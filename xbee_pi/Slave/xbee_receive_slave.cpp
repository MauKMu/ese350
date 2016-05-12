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

// "Protocol"
// Pi master asks to read byte from mbed
// if mbed sends 0x00 as FIRST BYTE, we want to send just IMU
// else, we want to sync
// Pi master is happy with data :) >:) >B)

#include "mbed.h"
#include "XBeeLib.h"
#if defined(ENABLE_LOGGING)
#include "DigiLoggerMbedSerial.h"
using namespace DigiLog;
#endif

#define BUFFER_SIZE             20
#define WANT_TO_SEND_JUST_IMU   0
#define WANT_TO_SYNC            1

using namespace XBeeLib;

Timer timer;
Serial *log_serial;
I2CSlave slave(p28, p27); // sda, scl



int i2c_status;

bool you_got_mail = false;
bool was_pi = false;
bool sent_data = false;
bool sent_pi_data = false;
bool got_new_data = false;
int packets_since_last_update;
char imu_data[4];
uint16_t imu_addr;
char buf[BUFFER_SIZE];

static void receive_cb_pi(const RemoteXBee802& remote, bool broadcast, const uint8_t *const data, uint16_t len)
{
    if (len > BUFFER_SIZE) {
        return;
    }
    // keep first byte: if 0x00, it's just IMU data, otherwise, it's sync data
    for (int i = 0; i < len; ++i) {
        buf[i] = data[i];    
    } 
    got_new_data = true;
    you_got_mail = true;
    was_pi = true;
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
    slave.address(0x07 << 1);
    timer.start();
    log_serial = new Serial(DEBUG_TX, DEBUG_RX);
    log_serial->baud(9600);

#if defined(ENABLE_LOGGING)
    new DigiLoggerMbedSerial(log_serial, LogLevelInfo);
#endif

    XBee802 xbee_d = XBee802(RADIO_TX_D, RADIO_RX_D, RADIO_RESET_D, NC, NC, 57600);
    /* Register callback */
    xbee_d.register_receive_cb(&receive_cb_pi);

    RadioStatus const radioStatusD = xbee_d.init();
    MBED_ASSERT(radioStatusD == Success);

    while (true) {
        timer.reset();
        packets_since_last_update = 0;
        xbee_d.process_rx_frames();
        //wait_ms(40);
        sent_pi_data = false;
        do {
            i2c_status = slave.receive();
            switch (i2c_status) {
                case I2CSlave::ReadAddressed:
                    // master wants to read data
                    // if we don't have new data, say so in the sent data
                    slave.write(buf, BUFFER_SIZE);
                    got_new_data = false;
                    sent_pi_data = true;
                    //log_serial->printf("  AAAAAA ");
                    break;
                default:
                    slave.write(0xFF);
                    break;
            }
            //log_serial->printf("i: %d ",i2c_status);
        } while (!sent_pi_data && timer.read_us() < 37000);
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
