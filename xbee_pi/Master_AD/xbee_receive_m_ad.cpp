/**
 * Copyright (c) 2015 Digi International Inc.,
 * All rights not expressly granted are reserved.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this file,
 * You can obtain one at http://mozilla.org/MPL/2.0/.
 *
 * Digi International Inc. 11001 Bren Road East, Minnetonka, MN 55343
 * =======================================================================
 */
// "Protocol" for transmitting Pi data
// Pi master asks to send data to mbed
// mbed reads it, and just broadcasts it to other mbeds
// the data includes a byte that says if it's supposed to be IMU data or sync data!
#include "mbed.h"
#include "XBeeLib.h"
#if defined(ENABLE_LOGGING)
#include "DigiLoggerMbedSerial.h"
using namespace DigiLog;
#endif

#define BUFFER_SIZE     10

using namespace XBeeLib;

Timer timer;
Serial *log_serial;
I2CSlave slave(p28, p27); // sda, scl

int i2c_status;

bool you_got_mail = false;
bool was_pi = false;
bool sent_data = false;
bool sent_pi_data = false;
int packets_since_last_update;
char imu_data[4] = {0, 0, 0, 0};
uint16_t imu_addr;
char buf[BUFFER_SIZE];

static void receive_cb(const RemoteXBee802& remote, bool broadcast, const uint8_t *const data, uint16_t len)
{
/*    if (remote.is_valid_addr16b()) {
        //log_serial->printf("Got a %s 16-bit RX packet [%04x], len %d\r\nData: ", broadcast ? "BROADCAST" : "UNICAST", remote.get_addr16(), len);
    } else {
        //log_serial->printf("Got a %s 64-bit RX packet [%08x:%08x], len %d\r\nData: ", broadcast ? "BROADCAST" : "UNICAST", remote.get_addr64(), len);
    }

    for (int i = 0; i < len; i++);
        //log_serial->printf("%02x ", data[i]);
*/
    if (remote.is_valid_addr16b()) {
        imu_addr = remote.get_addr16();
        switch (imu_addr) {
            case 0xAAA1:
                imu_data[0] = data[0];
                //log_serial->printf("*A1*");
                break;
            case 0xAAA2:
                imu_data[1] = data[0];
                //log_serial->printf("*A2*");
                break;    
            default:
                log_serial->printf("*%4x*", imu_addr);
        }
    } else {
        imu_addr = remote.get_addr64();
        log_serial->printf(" 64 ");    
    }        
    you_got_mail = true;
    ++packets_since_last_update;
}

static void receive_cb_pi(const RemoteXBee802& remote, bool broadcast, const uint8_t *const data, uint16_t len)
{
    you_got_mail = true;
    was_pi = true;
    ++packets_since_last_update;
}

static void send_data(XBee802& xbee, char data[], int len) {
    const TxStatus txStatus = xbee.send_data_broadcast((const uint8_t *)data, len);    
    if (txStatus == TxStatusSuccess) {
        sent_pi_data = true;
        log_serial->printf("SENT");
    }    
}

int main()
{
    slave.stop();
    slave.frequency(100000);
    // for some reason this is neither this method doesn't take the actual 7-bit address.
    // update: that is mentioned in the library, but in a sorta confusing way. noice
    // instead, it takes (7-bit address << 1) i.e. 7-bit address shifted by 1 bit to left
    // so write parameter as 7_BIT_ADDRESS << 1
    slave.address(0x07 << 1);
    timer.start();
    log_serial = new Serial(DEBUG_TX, DEBUG_RX);
    log_serial->baud(9600);

#if defined(ENABLE_LOGGING)
    new DigiLoggerMbedSerial(log_serial, LogLevelInfo);
#endif

    XBee802 xbee_a = XBee802(RADIO_TX, RADIO_RX, RADIO_RESET, NC, NC, 57600);
    XBee802 xbee_d = XBee802(RADIO_TX_D, RADIO_RX_D, RADIO_RESET_D, NC, NC, 57600);
    /* Register callback */
    xbee_a.register_receive_cb(&receive_cb);
    xbee_d.register_receive_cb(&receive_cb_pi);

    RadioStatus const radioStatusA = xbee_a.init();
    MBED_ASSERT(radioStatusA == Success);

    RadioStatus const radioStatusD = xbee_d.init();
    MBED_ASSERT(radioStatusD == Success);

    while (true) {
        timer.reset();
        packets_since_last_update = 0;
        xbee_a.process_rx_frames();
        xbee_d.process_rx_frames();
        //wait_ms(40);
        sent_data = false;
        sent_pi_data = false;
        do {
            i2c_status = slave.receive();
            switch (i2c_status) {
                case I2CSlave::ReadAddressed:
                    // master wants to read IMU data
                    slave.write(imu_data, 2);
                    sent_data = true;
                    //log_serial->printf("  AAAAAA ");
                    break;
                case I2CSlave::WriteGeneral:
                    // master wants to send data to other Pis
                    slave.read(buf, BUFFER_SIZE);
                    log_serial->printf("**%2x**", buf[0]);
                    log_serial->printf("**%2x**", buf[1]);
                    log_serial->printf("**%2x**", buf[2]);
                    //log_serial->printf(" %2x ", buf[0]);
                    send_data(xbee_d, buf, BUFFER_SIZE);
                    //sent_pi_data = true;
                    break;
                // it makes literally no sense, but this has to be here
                default:
                    slave.write(0xFF);
                    break;
            }
            //log_serial->printf("i: %d ",i2c_status);
        } while (!sent_data && !sent_pi_data && timer.read_us() < 37000);
        while (timer.read_us() < 40000);       
        log_serial->printf("Took %d us...  |  ", timer.read_us());
        if (you_got_mail) {
            log_serial->printf("\n\rGOT %d | ", packets_since_last_update);
            if (was_pi)
                log_serial->printf("Pi! | ");
            you_got_mail = false;
            was_pi = false;
        }
    }

    delete(log_serial);
}
