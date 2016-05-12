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

#include "mbed.h"
#include "XBeeLib.h"
#if defined(ENABLE_LOGGING)
#include "DigiLoggerMbedSerial.h"
using namespace DigiLog;
#endif

using namespace XBeeLib;

Timer timer;
Serial *log_serial;
I2CSlave slave(p28, p27); // sda, scl

int i2c_status;

bool you_got_mail = false;
bool was_pi = false;
bool sent_data = false;
int packets_since_last_update;
char imu_data[4];
uint16_t imu_addr;

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
            case 0xCCC1:
                imu_data[0] = data[0];
                //log_serial->printf("*C1*");
                break;
            case 0xCCC2:
                imu_data[1] = data[0];
                //log_serial->printf("*C2*");
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

int main()
{
    slave.stop();
    slave.frequency(100000);
    // for some reason this is neither this method doesn't take the actual 7-bit address.
    // update: that is mentioned in the library, but in a sorta confusing way. noice
    // instead, it takes (7-bit address << 1) i.e. 7-bit address shifted by 1 bit to left
    // so write parameter as 7_BIT_ADDRESS << 1
    slave.address(0x08 << 1);
    timer.start();
    log_serial = new Serial(DEBUG_TX, DEBUG_RX);
    log_serial->baud(9600);

#if defined(ENABLE_LOGGING)
    new DigiLoggerMbedSerial(log_serial, LogLevelInfo);
#endif

    XBee802 xbee_c = XBee802(RADIO_TX, RADIO_RX, RADIO_RESET, NC, NC, 57600);
    /* Register callback */
    xbee_c.register_receive_cb(&receive_cb);

    RadioStatus const radioStatusC = xbee_c.init();
    MBED_ASSERT(radioStatusC == Success);

    while (true) {
        timer.reset();
        packets_since_last_update = 0;
        xbee_c.process_rx_frames();
        //wait_ms(40);
        sent_data = false;
        do {
            i2c_status = slave.receive();
            switch (i2c_status) {
                case I2CSlave::ReadAddressed:
                    slave.write(imu_data, 2);
                    sent_data = true;
                    //log_serial->printf("  AAAAAA ");
                    break;
                // it makes literally no sense, but this has to be here
                default:
                    slave.write(0xFF);
                    break;
            }
            //log_serial->printf("i: %d ",i2c_status);
        } while (!sent_data && timer.read_us() < 37000);
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
