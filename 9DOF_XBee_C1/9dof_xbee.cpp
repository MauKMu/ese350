#include "mbed.h"
#include "XBeeLib.h"
#if defined(ENABLE_LOGGING)
#include "DigiLoggerMbedSerial.h"
using namespace DigiLog;
#endif

#define REMOTE_NODE_ADDR64_MSB  ((uint32_t)0x0013A200)

//#error "Replace next define with the LSB of the remote module's 64-bit address (SL parameter)"
#define REMOTE_NODE_ADDR64_LSB  ((uint32_t)0x4091276E)

//#error "Replace next define with the remote module's 16-bit address (MY parameter)"
#define REMOTE_NODE_ADDR16      ((uint16_t)0xCCC0)
// sending to AAA0

#define REMOTE_NODE_ADDR64      UINT64(REMOTE_NODE_ADDR64_MSB, REMOTE_NODE_ADDR64_LSB)

// address that "clears" this module, i.e. after receiving a broadcast from this node,
// this node will start sending data
#define CLEARING_ADDR           0xCCC2

using namespace XBeeLib;

#define PRINT_ACCELERATION  1
#define PRINT_TILT          1

//#define M_PI            3.14159265358979323846 
#define RAD_TO_DEG          57.2957795131 // 180/pi
#define DEG_TO_RAD          0.01745329251 // pi/180
#define TALK_TO_ACCEL       1
#define TALK_TO_GYRO        0
#define ALONG_X             0 // for use with
#define ALONG_Y             1 // gravity_axis
#define ALONG_Z             2
#define GYRO_WEIGHT         0.9
#define ACCEL_WEIGHT        0.1
#define ALT_GYRO_WEIGHT     0.80
#define ALT_ACCEL_WEIGHT    0.20
#define TILT_Y_THRESHOLD    15.0f
#define TILT_X_THRESHOLD    18.0f
#define SHAKE_THRESHOLD     0.7f
#define SHAKE_COUNTER_MAX   3
/* OBSOLETE
#define VERTICAL_TILT       0
#define HORIZONTAL_TILT     1
#define XY_FORCE            2
#define Z_FORCE             3 */
#define UP_DOWN_BIT             7
#define UP_DOWN_INTENSITY       5
#define LEFT_RIGHT_BIT          4
#define LEFT_RIGHT_INTENSITY    2
#define SHAKE_BIT               1

/*
 * Filter out high gyroscope outputs (spikes) by maintaining weighted array [1/2,1/3,1/6] from which weighted average of last 3 outputs is calculated?
 * Or maybe simpler approach of just keeping latest output (as opposed to latest output) 
 */

Timer timer;
Serial *log_serial;
DigitalOut myled(LED1);
I2C i2c(p28, p27);  // sda, scl
Serial pc(USBTX, USBRX);

const int ACCEL_ADDR_W = 0x32;
const int ACCEL_ADDR_R = 0x33;

const int GYRO_ADDR_W = 0xD6;
const int GYRO_ADDR_R = 0xD7;

const int ACCEL_CTRL_REG1_A = 0x20;
const int ACCEL_CTRL_REG4_A = 0x23;
const int GYRO_CTRL_REG1 = 0x20;
const int GYRO_CTRL_REG4 = 0x23;

const int ACCEL_OUT_X_L_A = 0x28;
const int ACCEL_OUT_X_H_A = 0x29;
const int ACCEL_OUT_Y_L_A = 0x2A;
const int ACCEL_OUT_Y_H_A = 0x2B;
const int ACCEL_OUT_Z_L_A = 0x2C;
const int ACCEL_OUT_Z_H_A = 0x2D;

const int GYRO_OUT_X_L_A = 0x28;
const int GYRO_OUT_X_H_A = 0x29;
const int GYRO_OUT_Y_L_A = 0x2A;
const int GYRO_OUT_Y_H_A = 0x2B;
const int GYRO_OUT_Z_L_A = 0x2C;
const int GYRO_OUT_Z_H_A = 0x2D;

int current_time;
const int LOOP_TIME_US = 40000; // it seems we can get data from IMU and perform some calculations in about 5ms.
                                // XBee takes 46ms for failed transmissions. so be safe and put 60ms as limit
const float LOOP_TIME_S = 0.000001 * LOOP_TIME_US;

int lo;
int hi;
short int accel_x, accel_y, accel_z;
short int gyro_x, gyro_y, gyro_z;
char gravity_axis;

char shake_counter = 0;

float a_x, a_y, a_z;    // normalized accel values
float avg_a_x, avg_a_y;
float a_magnitude;
float adjusted_x, adjusted_y, adjusted_z;
float adjusted_magnitude;
float g_magnitude;
float acc_angle_x, acc_angle_y, acc_angle_z;
float g_x, g_y, g_z;    // normalized gyro values
float last_g_x[3], last_g_y[3], last_g_z[3];    // values will be averaged over time
float last_good_angle_z;
float z_axis_x, z_axis_y, z_axis_z;
float last_z_axis_x[3], last_z_axis_y[3], last_z_axis_z[3];
float last_angle_x, last_angle_y, last_angle_z;
float corrected_a_x, corrected_a_y, corrected_a_z;
float angle_x, angle_y, angle_z; // angle around y,z axes: [-180,180]
                        // y: starts at z axis, increases towards x
                        // z: starts at x, increases towards y
                        // this system relies on atan2 and requires two angles
                        // could store three angles that go from [0,180] and more directly restore cartesian coords like that
                        
char xbee_data[4];      //[UP, LEFT, DOWN, RIGHT]
char xbee_send_counter = 0;
uint16_t imu_addr;
uint8_t raw_xbee_data = 0;
bool cleared_for_sending = true;
char havent_sent_counter = 0;

// ========== HELPER FUNCTIONS ===============

/**
  * Sends data through XBee. Yep!
**/
static void send_data(XBee802& xbee, const RemoteXBee802& RemoteDevice, char data[], int len) {
    const TxStatus txStatus = xbee.send_data_broadcast((const uint8_t *)data, len);    
    if (txStatus == TxStatusSuccess) {
        cleared_for_sending = false;    
        havent_sent_counter = 0;
    }    
}

/**
  * Callback function for handling frames.
**/
static void receive_cb(const RemoteXBee802& remote, bool broadcast, const uint8_t *const data, uint16_t len)
{
    if (remote.is_valid_addr16b()) {
        imu_addr = remote.get_addr16();
        switch (imu_addr) {
            case CLEARING_ADDR :
                cleared_for_sending = true;
                break;
        }
    }
}

/**
  * Attempts to write "value" to register at subaddress "sub".
  * Returns 0 if successful, 1 otherwise.
**/
int i2c_write(char sub, char value, char which_chip) {
    char addr;
    
    if (which_chip)
        addr = ACCEL_ADDR_W;
    else
        addr = GYRO_ADDR_W;
        
    // send ST
    i2c.start();
    
    // send SAD+W, i.e. main address + write byte
    if (!i2c.write(addr)) {
        pc.printf("Error: failed to get ACK after sending SAD+W\n\r");
        pc.printf("%d\n",which_chip);
        return 1;
    }
    
    // send SUB, i.e. subaddress of register we want to read    
    if (!i2c.write(sub)) {
        pc.printf("Error: failed to get ACK after sending SUB\n\r");
        return 1;
    }
        
    // send values to initialize reg1 with    
    if (!i2c.write(value)) {
        pc.printf("Error: failed to get ACK after sending initial value for REG1_A\n\r");
        return 1;
    }

    // send SP
    i2c.stop();    
    
    return 0;
}

/**
  * Attempts to read data in register at subaddress "sub" and store it in variable "dest".
  * Returns 0 if successful, 1 otherwise.
**/
int i2c_read(char sub, int* dest, char which_chip) {
    char addr;
    
    if (which_chip)
        addr = ACCEL_ADDR_W;
    else
        addr = GYRO_ADDR_W;
    
    // send ST
    i2c.start();
    
    // send SAD+W, i.e. main address + write byte
    if (!i2c.write(addr)) {
        pc.printf("Error: failed to get ACK after sending SAD+W\n\r");
            return 1;
    }
    
    // send SUB, i.e. subaddress of register we want to read    
    if (!i2c.write(sub)) {
        pc.printf("Error: failed to get ACK after sending SUB\n\r");
            return 1;
    }
    
    // send SR, which is a repeated start signal. i don't know why???
    i2c.start();

    if (which_chip)
        addr = ACCEL_ADDR_R;
    else
        addr = GYRO_ADDR_R;
    
    // send SAD+R, i.e. main address + read byte
    if (!i2c.write(addr)) {

        pc.printf("Error: failed to get ACK after sending SAD+R\n\r");        
        return 1;
    }
    
    // finally read in DATA, do NOT send ACK so we can stop communication in next step
    *dest = i2c.read(0);
    
    i2c.stop();    
    
    return 0;
}

void update_accel_xyz() {
    i2c_read(ACCEL_OUT_X_L_A, &lo, TALK_TO_ACCEL);
    i2c_read(ACCEL_OUT_X_H_A, &hi, TALK_TO_ACCEL);
    
    accel_x = (hi << 8) | lo;
    
    //pc.printf("ACCEL - X - Got: %02x%02x = %d\n\r",hi, lo, accel_x);
    
    i2c_read(ACCEL_OUT_Y_L_A, &lo, TALK_TO_ACCEL);
    i2c_read(ACCEL_OUT_Y_H_A, &hi, TALK_TO_ACCEL);
    
    accel_y = (hi << 8) | lo;
    
    //pc.printf("ACCEL - Y - Got: %02x%02x = %d\n\r",hi, lo, accel_y);
    
    i2c_read(ACCEL_OUT_Z_L_A, &lo, TALK_TO_ACCEL);
    i2c_read(ACCEL_OUT_Z_H_A, &hi, TALK_TO_ACCEL);
    
    accel_z = (hi << 8) | lo;    
}

int main() {

    log_serial = &pc;
    
#if defined(ENABLE_LOGGING)
    new DigiLoggerMbedSerial(log_serial, LogLevelInfo);
#endif

    pc.printf("Setting up XBee...\n\r");

    XBee802 xbee = XBee802(RADIO_TX, RADIO_RX, RADIO_RESET, NC, NC, 57600);
    xbee.register_receive_cb(&receive_cb);

    RadioStatus radioStatus = xbee.init();
    MBED_ASSERT(radioStatus == Success);
    
    const RemoteXBee802 remoteDevice16b = RemoteXBee802(REMOTE_NODE_ADDR16);

    timer.start();
    i2c.frequency(100000);
    
    // set up registers in LSM303DLHC (accelerometer)
    
    // turn it on
    i2c_write(ACCEL_CTRL_REG1_A, 0x97, TALK_TO_ACCEL); // Pro refactoring, design patterns, etc. Google should hire me already, clearly
    // set scale to +/- 8G (for now), and set high-res mode on
    i2c_write(ACCEL_CTRL_REG4_A, 0x28, TALK_TO_ACCEL);


    // set up registers in L3GD20 (gyroscope)
    
    // resetting it doesn't seem to change much
    //i2c_write(0x24, 0x80, TALK_TO_GYRO);
    i2c_write(GYRO_CTRL_REG1, 0x0F, TALK_TO_GYRO);
    i2c_write(GYRO_CTRL_REG4, 0x10, TALK_TO_GYRO);

    // get initial gravity
    pc.printf("Place controller in stable, flat position...\n\r");
    g_magnitude = 0.0;
    while (abs(g_magnitude - 1.0) > 0.1) {
        update_accel_xyz();
        a_x = (float)(accel_x) / 4096;                
        a_y = (float)(accel_y) / 4096;
        a_z = (float)(accel_z) / 4096;
        g_magnitude = sqrt(a_x*a_x + a_y*a_y + a_z*a_z);
    }
    // for simplicity's sake, assume gravity is along z
    gravity_axis = ALONG_Z;
    avg_a_x = a_x;
    avg_a_y = a_y;
    //angle_y = acos(a_z / g_magnitude) * RAD_TO_DEG;
    angle_x = atan2(a_y, a_z) * RAD_TO_DEG;
    angle_y = atan2(a_x, a_z) * RAD_TO_DEG;
    angle_z = atan2(a_y, a_x) * RAD_TO_DEG;
    last_good_angle_z = angle_z;
    //pc.printf("Initial y angle: %7.4f\n\r",angle_y);
    //pc.printf("Initial z angle: %7.4f\n\r",angle_z);
    
    // initialize g_x/y/z arrays
    
    i2c_read(GYRO_OUT_X_L_A, &lo, TALK_TO_GYRO);
    i2c_read(GYRO_OUT_X_H_A, &hi, TALK_TO_GYRO);
    
    gyro_x = (hi << 8) | lo;
    
    last_g_x[0] = (float)(gyro_x) * 0.01750f;
    last_g_x[1] = last_g_x[0];
    last_g_x[2] = last_g_x[0];
    
    i2c_read(GYRO_OUT_Y_L_A, &lo, TALK_TO_GYRO);
    i2c_read(GYRO_OUT_Y_H_A, &hi, TALK_TO_GYRO);
    
    gyro_y = (hi << 8) | lo;
    
    last_g_y[0] = (float)(gyro_y) * 0.01750f;
    last_g_y[1] = last_g_y[0];
    last_g_y[2] = last_g_y[0];
    
    i2c_read(GYRO_OUT_Z_L_A, &lo, TALK_TO_GYRO);
    i2c_read(GYRO_OUT_Z_H_A, &hi, TALK_TO_GYRO);
    
    gyro_z = (hi << 8) | lo;
    
    last_g_z[0] = (float)(gyro_z) * 0.01750f;
    last_g_z[1] = last_g_z[0];
    last_g_z[2] = last_g_z[0];
    
    // initialize z_axis_x/y/z arrays
    
    last_z_axis_x[0] = 0.0f;
    last_z_axis_x[1] = 0.0f;
    last_z_axis_x[2] = 0.0f;
    
    last_z_axis_y[0] = 0.0f;
    last_z_axis_y[1] = 0.0f;
    last_z_axis_y[2] = 0.0f;
    
    last_z_axis_z[0] = 0.0f;
    last_z_axis_z[1] = 0.0f;
    last_z_axis_z[2] = 0.0f;
    
    pc.printf("Entering main loop...\n\r");
    
    while(1) {
        //pc.printf("Press any key to get data.\r\n");
        //pc.getc();
        timer.reset();
        
        i2c_read(ACCEL_OUT_X_L_A, &lo, TALK_TO_ACCEL);
        i2c_read(ACCEL_OUT_X_H_A, &hi, TALK_TO_ACCEL);
        
        accel_x = (hi << 8) | lo;
        
        //pc.printf("ACCEL - X - Got: %02x%02x = %d\n\r",hi, lo, accel_x);
        
        i2c_read(ACCEL_OUT_Y_L_A, &lo, TALK_TO_ACCEL);
        i2c_read(ACCEL_OUT_Y_H_A, &hi, TALK_TO_ACCEL);
        
        accel_y = (hi << 8) | lo;
        
        //pc.printf("ACCEL - Y - Got: %02x%02x = %d\n\r",hi, lo, accel_y);
        
        i2c_read(ACCEL_OUT_Z_L_A, &lo, TALK_TO_ACCEL);
        i2c_read(ACCEL_OUT_Z_H_A, &hi, TALK_TO_ACCEL);
        
        accel_z = (hi << 8) | lo;
        
        //pc.printf("ACCEL - Z - Got: %02x%02x = %d\n\r",hi, lo, accel_z);
                        
        a_x = (float)(accel_x) / 4096;                
        a_y = (float)(accel_y) / 4096;
        a_z = (float)(accel_z) / 4096;
        
        a_magnitude = sqrt(a_x*a_x + a_y*a_y + a_z*a_z);
        
        //pc.printf("ACCEL: (%6.4f, %6.4f, %6.4f)\n\r", a_x, a_y, a_z);
        
        //pc.printf("MAGNITUDE: %6.4f\n\r", (sqrt(a_x*a_x + a_y*a_y + a_z*a_z)) );

                
        i2c_read(GYRO_OUT_X_L_A, &lo, TALK_TO_GYRO);
        i2c_read(GYRO_OUT_X_H_A, &hi, TALK_TO_GYRO);
        
        gyro_x = (hi << 8) | lo;
        
        //pc.printf("GYRO  - X - Got: %02x%02x = %d\n\r",hi, lo, gyro_x);
        
        i2c_read(GYRO_OUT_Y_L_A, &lo, TALK_TO_GYRO);
        i2c_read(GYRO_OUT_Y_H_A, &hi, TALK_TO_GYRO);
        
        gyro_y = (hi << 8) | lo;
        
        //pc.printf("GYRO  - Y - Got: %02x%02x = %d\n\r",hi, lo, gyro_y);
        
        i2c_read(GYRO_OUT_Z_L_A, &lo, TALK_TO_GYRO);
        i2c_read(GYRO_OUT_Z_H_A, &hi, TALK_TO_GYRO);
        
        gyro_z = (hi << 8) | lo;
        
        //pc.printf("GYRO  - Z - Got: %02x%02x = %d\n\r",hi, lo, gyro_z);

        //g_x = (float)(gyro_x) * 0.01750f;
        //g_y = (float)(gyro_y) * 0.01750f;
        //g_z = (float)(gyro_z) * 0.01750f;
        
        last_g_x[2] = last_g_x[1];
        last_g_x[1] = last_g_x[0];
        last_g_x[0] = (float)(gyro_x) * 0.01750f;
        
        g_x = last_g_x[0] / 2.0f + last_g_x[1] / 3.0f + last_g_x[2] / 6.0f;
        
        last_g_y[2] = last_g_y[1];
        last_g_y[1] = last_g_y[0];
        last_g_y[0] = (float)(gyro_y) * 0.01750f;
        
        g_y = last_g_y[0] / 2.0f + last_g_y[1] / 3.0f + last_g_y[2] / 6.0f;
        
        last_g_z[2] = last_g_z[1];
        last_g_z[1] = last_g_z[0];
        last_g_z[0] = (float)(gyro_z) * 0.01750f;
        
        g_z = last_g_z[0] / 2.0f + last_g_z[1] / 3.0f + last_g_z[2] / 6.0f;
        
        // gravity is along which axis? (i.e. what is axis with largest acceleration component)
        // alternative way: check if axes are less than some arbitrary value...?
        if (abs(a_x) > abs(a_y)) {
            if (abs(a_x) > abs(a_z)) {
                if (gravity_axis == ALONG_Y) {
                    // "refresh" angle_y
                    // assume angle_x and angle_z are reliable
                    angle_y = atan2(cos(angle_z * DEG_TO_RAD),cos(angle_x * DEG_TO_RAD));    
                } else if (gravity_axis == ALONG_Z) {
                    // "refresh" angle_z
                    // assume angle_x and angle_y are reliable
                    angle_z = atan2(sin(angle_x * DEG_TO_RAD),sin(angle_y * DEG_TO_RAD));                
                }
                gravity_axis = ALONG_X;   
            } else {
                if (gravity_axis == ALONG_X) {
                    // "refresh" angle_x
                    // assume angle_y and angle_z are reliable
                    angle_x = atan2(sin(angle_z * DEG_TO_RAD),cos(angle_y * DEG_TO_RAD));        
                } else if (gravity_axis == ALONG_Y) {
                    // "refresh" angle_y
                    // assume angle_x and angle_z are reliable
                    angle_y = atan2(cos(angle_z * DEG_TO_RAD),cos(angle_x * DEG_TO_RAD));    
                }
                gravity_axis = ALONG_Z;    
            }
        } else {
            // then a_y >= a_z
            if (abs(a_y) > abs(a_z)) {
                if (gravity_axis == ALONG_X) {
                    // "refresh" angle_x
                    // assume angle_y and angle_z are reliable
                    angle_x = atan2(sin(angle_z * DEG_TO_RAD),cos(angle_y * DEG_TO_RAD));        
                } else if (gravity_axis == ALONG_Z) {
                    // "refresh" angle_z
                    // assume angle_x and angle_y are reliable
                    angle_z = atan2(sin(angle_x * DEG_TO_RAD),sin(angle_y * DEG_TO_RAD));                
                }
                gravity_axis = ALONG_Y;   
            } else {
                if (gravity_axis == ALONG_X) {
                    // "refresh" angle_x
                    // assume angle_y and angle_z are reliable
                    angle_x = atan2(sin(angle_z * DEG_TO_RAD),cos(angle_y * DEG_TO_RAD));        
                } else if (gravity_axis == ALONG_Y) {
                    // "refresh" angle_y
                    // assume angle_x and angle_z are reliable
                    angle_y = atan2(cos(angle_z * DEG_TO_RAD),cos(angle_x * DEG_TO_RAD));    
                }
                gravity_axis = ALONG_Z;    
            }    
        }
        // http://math.stackexchange.com/questions/180418/calculate-rotation-matrix-to-align-vector-a-to-vector-b-in-3d/476311#476311
        raw_xbee_data = 0;
        if (gravity_axis == ALONG_X) {
            // ignore yz plane / angle about x
            angle_y = (angle_y + g_y * LOOP_TIME_S) * GYRO_WEIGHT + atan2(a_x, a_z) * RAD_TO_DEG * ACCEL_WEIGHT;
            angle_z = (angle_z + g_z * LOOP_TIME_S) * GYRO_WEIGHT + atan2(a_y, a_x) * RAD_TO_DEG * ACCEL_WEIGHT;
            z_axis_x = sin(angle_y * DEG_TO_RAD);
            z_axis_y = sin(angle_z * DEG_TO_RAD);
            z_axis_z = cos(angle_y * DEG_TO_RAD);
            if (PRINT_TILT) {
                //xbee_data[VERTICAL_TILT] = 0x00;
                if (angle_y > TILT_Y_THRESHOLD) {
                    //pc.printf("Tilted up!\n\r");
                    //xbee_data[VERTICAL_TILT] = 0xf0;
                    raw_xbee_data |= (1 << UP_DOWN_BIT);  
                    raw_xbee_data |= (3 << UP_DOWN_INTENSITY);  
                } else if (angle_y < -TILT_Y_THRESHOLD) {
                    //pc.printf("Tilted down!\n\r");    
                    //xbee_data[VERTICAL_TILT] = 0x0f;
                    // assume bit in raw_xbee_data is 0
                    raw_xbee_data |= (3 << UP_DOWN_INTENSITY);
                }
                //xbee_data[HORIZONTAL_TILT] = 0x00;   
            }
            //pc.printf("Along X: (%5.4f, %5.4f, %5.4f)\r\n",z_axis_x,z_axis_y,z_axis_z);
            //pc.printf("Y Angle: %7.4f\n\r",angle_y);
            //pc.printf("Z Angle: %7.4f\n\r",angle_z);
        } else if (gravity_axis == ALONG_Y) {
            angle_x = (angle_x + g_x * LOOP_TIME_S) * GYRO_WEIGHT + atan2(a_y, a_z) * RAD_TO_DEG * ACCEL_WEIGHT;
            angle_z = (angle_z + g_z * LOOP_TIME_S) * GYRO_WEIGHT + atan2(a_y, a_x) * RAD_TO_DEG * ACCEL_WEIGHT;            
            z_axis_x = cos(angle_z * DEG_TO_RAD);
            z_axis_y = sin(angle_z * DEG_TO_RAD);
            z_axis_z = cos(angle_x * DEG_TO_RAD);
            if (PRINT_TILT) {
//                xbee_data[VERTICAL_TILT] = 0x00;
//                xbee_data[HORIZONTAL_TILT] = 0x00;
                if (angle_x > TILT_X_THRESHOLD) {
                    //pc.printf("Tilted right!\n\r");    
//                    xbee_data[HORIZONTAL_TILT] = 0x0f;
                    raw_xbee_data |= (3 << LEFT_RIGHT_INTENSITY);
                } else if (angle_x < -TILT_X_THRESHOLD) {
                    //pc.printf("Tilted left!\n\r");    
//                    xbee_data[HORIZONTAL_TILT] = 0xf0;
                    raw_xbee_data |= (1 << LEFT_RIGHT_BIT);
                    raw_xbee_data |= (3 << LEFT_RIGHT_INTENSITY);
                }    
            }
            //pc.printf("Along Y: (%5.4f, %5.4f, %5.4f)\r\n",z_axis_x,z_axis_y,z_axis_z);
            //pc.printf("X Angle: %7.4f\n\r",angle_x);
            //pc.printf("Z Angle: %7.4f\n\r",angle_z);
        } else {
            angle_x = (angle_x + g_x * LOOP_TIME_S) * GYRO_WEIGHT + atan2(a_y, a_z) * RAD_TO_DEG * ACCEL_WEIGHT;            
            angle_y = (angle_y + g_y * LOOP_TIME_S) * ALT_GYRO_WEIGHT + atan2(a_x, a_z) * RAD_TO_DEG * ALT_ACCEL_WEIGHT;
            z_axis_x = sin(angle_y * DEG_TO_RAD);
            z_axis_y = sin(angle_x * DEG_TO_RAD);
            z_axis_z = cos(angle_y * DEG_TO_RAD);
            if (PRINT_TILT) {
                //xbee_data[VERTICAL_TILT] = 0x00;
                if (angle_y > TILT_Y_THRESHOLD) {
                    //pc.printf("Tilted up!\n\r");  
//                    xbee_data[VERTICAL_TILT] = 0xf0;
                    raw_xbee_data |= (1 << UP_DOWN_BIT);  
                    raw_xbee_data |= (3 << UP_DOWN_INTENSITY);  
                } else if (angle_y < -TILT_Y_THRESHOLD) {
                    //pc.printf("Tilted down!\n\r");
//                    xbee_data[VERTICAL_TILT] = 0x0f;    
                    raw_xbee_data |= (3 << UP_DOWN_INTENSITY);  
                }    
//                xbee_data[HORIZONTAL_TILT] = 0x00;
                if (angle_x > TILT_X_THRESHOLD) {
                    //pc.printf("Tilted right!\n\r");    
//                    xbee_data[HORIZONTAL_TILT] = 0x0f;
                    raw_xbee_data |= (3 << LEFT_RIGHT_INTENSITY);
                } else if (angle_x < -TILT_X_THRESHOLD) {
                    //pc.printf("Tilted left!\n\r");    
//                    xbee_data[HORIZONTAL_TILT] = 0xf0;
                    raw_xbee_data |= (1 << LEFT_RIGHT_BIT);
                    raw_xbee_data |= (3 << LEFT_RIGHT_INTENSITY);
                }
            }
            //pc.printf("z_axis_x 1: %5.4f\n\r",z_axis_x);
            //pc.printf("z_axis_x 2: %5.4f\n\r",sqrt(1.0 -z_axis_y*z_axis_y -z_axis_z*z_axis_z));
            //pc.printf("Along Z: (%5.4f, %5.4f, %5.4f)\r\n",z_axis_x,z_axis_y,z_axis_z);
            //pc.printf("X Angle: %7.4f\n\r",angle_x);
            //pc.printf("Y Angle: %7.4f\n\r",angle_y);
        }
        
        // do "filtering"/averaging do filter out random spikes
        last_z_axis_x[2] = last_z_axis_x[1];
        last_z_axis_x[1] = last_z_axis_x[0];
        last_z_axis_x[0] = a_x / a_magnitude - z_axis_x;

        corrected_a_x = last_z_axis_x[0] / 2.0f + last_z_axis_x[1] / 3.0f + last_z_axis_x[2] / 6.0f;
        
        last_z_axis_y[2] = last_z_axis_y[1];
        last_z_axis_y[1] = last_z_axis_y[0];
        last_z_axis_y[0] = a_y / a_magnitude - z_axis_y;

        corrected_a_y = last_z_axis_y[0] / 2.0f + last_z_axis_y[1] / 3.0f + last_z_axis_y[2] / 6.0f;

        last_z_axis_z[2] = last_z_axis_z[1];
        last_z_axis_z[1] = last_z_axis_z[0];
        last_z_axis_z[0] = a_z / a_magnitude - z_axis_z;

        corrected_a_z = last_z_axis_z[0] / 2.0f + last_z_axis_z[1] / 3.0f + last_z_axis_z[2] / 6.0f;
        
        adjusted_magnitude = sqrt(corrected_a_x*corrected_a_x + corrected_a_y*corrected_a_y + corrected_a_z*corrected_a_z);

        if (abs(adjusted_magnitude) > SHAKE_THRESHOLD) {
            if (shake_counter > SHAKE_COUNTER_MAX) {
                raw_xbee_data |= (1 << SHAKE_BIT);   
                //pc.printf("Shakin\'!\n\r");
            } else {
                ++shake_counter;    
            }
        } else {
            shake_counter = 0;    
        }
        
        //pc.printf("a_x / a_magnitude: %5.4f\n\r",a_x / a_magnitude);
        /*if (PRINT_ACCELERATION) {
 //           xbee_data[XY_FORCE] = 0x00;
 //           xbee_data[Z_FORCE] = 0x00;
            if (abs(corrected_a_x) > 0.6) {
                if (abs(corrected_a_y < 0.3)) {
                    //pc.printf("Strong x-axis motion!\n\r");
                }    
                else if (abs(corrected_a_x > 0.75)) {
                    //pc.printf("Strong x-axis motion!\n\r");
                }
            }
            if (abs(corrected_a_y) > 0.4) {
                //pc.printf("Strong y-axis motion!\n\r");
                if (corrected_a_y > 0) {
//                    xbee_data[XY_FORCE] = 0x0f;
                    raw_xbee_data |= (1 << Y_AXIS_SIGN_BIT);
                } 
//                else 
//                    xbee_data[XY_FORCE] = 0xf0;    
                raw_xbee_data |= (1 << Y_AXIS_INTENSITY);
            }
            if (abs(corrected_a_z) > 0.7) {
                //pc.printf("Strong z-axis motion!\n\r");
                if (corrected_a_z > 0) {
//                    xbee_data[Z_FORCE] = 0x0f;
                    raw_xbee_data |= (1 << Z_AXIS_SIGN_BIT);
                }
//                else {
//                    xbee_data[Z_FORCE] = 0xf0;
                raw_xbee_data |= (1 << Z_AXIS_INTENSITY);
//                }    
            }
            //pc.printf("Acceleration: (%5.4f, %5.4f, %5.4f)\r\n",corrected_a_x,corrected_a_y,corrected_a_z);
        }*/
        // convert raw_xbee_data to array
        //pc.printf("%02x\n\r",raw_xbee_data);
        xbee_data[0] = (char)(raw_xbee_data);
        /*
        if (a_x >= 0) {
            // keep positive
            angle_y = (angle_y + g_y * LOOP_TIME_S) * 0.9 + acos(a_z / a_magnitude) * RAD_TO_DEG * 0.1;    
        } else {
            // change acos to negative
            angle_y = (angle_y + g_y * LOOP_TIME_S) * 0.9 - acos(a_z / a_magnitude) * RAD_TO_DEG * 0.1;    
        }*/
        //angle_y = (angle_y + g_y * LOOP_TIME_S) * 0.9 + acos(a_z / a_magnitude) * RAD_TO_DEG * 0.1;
        // do something if x or y or z = 0?
        // check if in range [-180,180]?
        //angle_y = (angle_y + g_y * LOOP_TIME_S) * 0.9 + atan2(a_x, a_z) * RAD_TO_DEG * 0.1;
        // reduce noise from gyroscope
        /*if (abs(g_z) < 10) {
            g_z *= 0.1;    
        }*/
        /*
        avg_a_x = avg_a_x * 0.6 + a_x * 0.4;
        avg_a_y = avg_a_y * 0.6 + a_y * 0.4;
        if (abs(a_x) < 0.075 && abs(a_y) < 0.075) {
            angle_z = angle_z + g_z * LOOP_TIME_S * 0.01;//(angle_z + g_z * LOOP_TIME_S) * 0.9 + angle_z * 0.1;
            //pc.printf("too small\n\r");            
        } else {
            last_good_angle_z = atan2(a_y, a_x) * RAD_TO_DEG;
            angle_z = (angle_z + g_z * LOOP_TIME_S) * 0.9 + atan2(a_y, a_x) * RAD_TO_DEG * 0.1;
            //last_good_angle_z = angle_z;    
            //pc.printf("normal\n\r");
        }*/
        //pc.printf("g_z:   %7.4f\n\r",g_z);
        //pc.printf("a_x:   %7.4f\n\r",a_x);
        //pc.printf("a_y:   %7.4f\n\r",a_y);
        //pc.printf("Y Angle: %7.4f\n\r",angle_y);
        //pc.printf("atan:    %7.4f\n\r",atan2(a_y, a_x) * RAD_TO_DEG * 0.1);
        //pc.printf("Z Angle: %7.4f\n\r",angle_z);
        
        // now we have accelerometer and gyroscope data...
        // use it to maintain a "real" xyz axis system, and project accel onto axes to see force direction??
        // http://www.starlino.com/imu_guide.html
        // https://www.youtube.com/watch?v=C7JQ7Rpwn2k
        // to speed up XBee:
        //      disable logging? doesn't help
        //      turn up BAUD rate? helps!
        // http://examples.digi.com/wp-content/uploads/2012/07/XBee_ZB_ZigBee_AT_Commands.pdf
        
        adjusted_x = a_x - g_x;
        adjusted_y = a_y - g_y;
        adjusted_z = a_z - g_z;
        
        //pc.printf("ADJUSTED: (%6.4f, %6.4f, %6.4f)\n\r", adjusted_x, adjusted_y, adjusted_z);
        
        adjusted_magnitude = sqrt(adjusted_x*adjusted_x + adjusted_y*adjusted_y + adjusted_z*adjusted_z);
        
        //pc.printf("ADJ. MAGN.: %6.4f\n\r", adjusted_magnitude);
        
/*        if (xbee_send_counter) {
            send_data(xbee, remoteDevice16b, xbee_data, 4);
        }
        
        xbee_send_counter = ~xbee_send_counter;  
*/        
        if (cleared_for_sending || havent_sent_counter > 6) {
            send_data(xbee, remoteDevice16b, xbee_data, 2);
            // cleared_for_sending updated in send_data    
        } else {
            xbee.process_rx_frames();    
            ++havent_sent_counter;
        }
        while (timer.read_us() < LOOP_TIME_US);
        
        pc.printf("Took %d us...\n\r", timer.read_us());
        
    }
}
