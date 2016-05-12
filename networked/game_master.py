from __future__ import print_function
import time
import pygame
import smbus
import random
import PyParticles_v00 as PyParticlesFrameRate
from pygame.locals import *

##### Convenient constants #####

# For left screen:      0
# For middle screen:    600
# For right screen:     1200
WIDTH_OFFSET = 0

# For left screen:      True
# For middle screen:    False
# For right screen:     True
IS_SLAVE = False

ROUND_TIME = 20.0
MSG_TIME = 5.0

# Hand indices
NONE = -1
UP = 0
LEFT = 1
RIGHT = 2
DOWN = 3

# Round status
TIE = 0
P1_WON = 1
P2_WON = 2

# python 2 has no enums, lol
TEAM_1 = 1
TEAM_2 = 2

# control things
H_NO_TILT = 0
H_LEFT_TILT = 1
H_LEFT_TILT_STRONG = 2
H_RIGHT_TILT = 3
H_RIGHT_TILT_STRONG = 4

V_NO_TILT = 0
V_UP_TILT = 1
V_UP_TILT_STRONG = 2
V_DOWN_TILT = 3
V_DOWN_TILT_STRONG = 4

S_NO_SHAKE = 0
S_SHAKE = 1

h_1_tilt = H_NO_TILT
h_2_tilt = H_NO_TILT

v_1_tilt = V_NO_TILT
v_2_tilt = V_NO_TILT

s_1 = S_NO_SHAKE
s_2 = S_NO_SHAKE

imu_data = [0]*4

ENABLE_I2C = True

# i2c things
MBED_ADDRESS_AC = 0x07  # these two
MBED_ADDRESS_D  = 0x08  # are for the master Pi
 
MBED_ADDRESS_SLAVE = 0x07   # this is for the slave Pi

SYNC_COUNTER_MAX = 10
sync_counter = 0
test_data = bytes([0xAB, 0xCD, 0xEF, 0x00, 0x00, 0x99, 0x99])


### HELPER FUNCTIONS #####

def get_new_card(numbers):
    if (len(numbers) < 1):
        print("Can't get cards from empty deck!")
        return -1
    index = random.randint(0, len(numbers)-1)
    val = numbers[index]
    del numbers[index]
    return val

def lookup_card(value):
    return {
        0: ["DOG",5,2,7,8],
        1: ["CAT",6,3,5,8],
        2: ["TIGER",10,9,6,3],
        3: ["LION",8,10,6,1],
        4: ["MOUSE",3,3,2,5],
        5: ["TOUCAN",7,2,4,6],
        6: ["GORILLA",6,5,9,4],
        7: ["SLOTH",1,1,3,10],
        8: ["SQUIRREL",5,2,5,9],
        9: ["PIG",4,4,7,7],
        10: ["RHINO",5,7,6,2],
        11: ["FOX",8,4,5,6],
        12: ["SHARK",9,9,3,2],
        13: ["MAN",3,6,10,5],
        14: ["DOLPHIN",7,3,9,8],
        15: ["SNAKE",2,8,4,3],
    }.get(value, ["GOD", 10, 10, 10, 10])

def draw_card(value, x_pos, y_pos):
    stats = lookup_card(value)
    name = font.render(stats[0], 1, (0,0,0), (123,123,123))
    speed = midfont.render("Speed: %i" % stats[1], 1, (0,0,0))
    fierceness = midfont.render("Fierceness: %i" % stats[2], 1, (0,0,0))
    intelligence = midfont.render("Intelligence: %i" % stats[3], 1, (0,0,0))
    cuteness = midfont.render("Cuteness: %i" % stats[4], 1, (0,0,0))
    screen.blit(name, (x_pos, y_pos))
    screen.blit(speed, (x_pos, 200+y_pos))
    screen.blit(fierceness, (x_pos, 275+y_pos))
    screen.blit(intelligence, (x_pos, 350+y_pos))
    screen.blit(cuteness, (x_pos, 425+y_pos))

def int_to_stat(index):
    if (index == 0):
        return "speed"
    elif (index == 1):
        return "fierceness"
    elif (index == 2):
        return "intelligence"
    elif (index == 3):
        return "cuteness"
    else:
        return ""

bus = smbus.SMBus(1) # open /dev/i2c-1 <- 1, not 0
print("Opened i2c bus! Setting up pygame...")

pygame.display.set_caption('Chaos')

(width, height) = (1920, 1023)
#screen = pygame.display.set_mode((width, height),pygame.NOFRAME | pygame.FULLSCREEN)
screen = pygame.display.set_mode((width, height),pygame.NOFRAME)

clock = pygame.time.Clock()

#initializes font modulep
pygame.init()

#initialize font
font = pygame.font.SysFont("comicsansms", 100)
midfont = pygame.font.SysFont("comicsansms", 50)


running = True

#clock.tick_busy_loop(25)

while running:
    waiting_to_start = True
    while waiting_to_start:
        screen.fill((128, 128, 128))

        pygame.display.flip()
            
        if IS_SLAVE:
            data_slave = [0]
            try:
                data_slave = bus.read_i2c_block_data(MBED_ADDRESS_SLAVE, 1, 1)
            except IOError:
                print("Timeout")
            if data_slave[0] == 0x03:
                waiting_to_start = False
        else:
            try:
                for event in pygame.event.get():
                    if event.type == pygame.KEYDOWN:
                        '''
                        start_byte = [0x03, 0x03]
                        bus.write_i2c_block_data(0, 1, start_byte) # must send to address 0 = "write general"
                        time.sleep(0.02)
                        bus.write_i2c_block_data(0, 1, start_byte) # must send to address 0 = "write general"
                        #clock.tick_busy_loop(25) # wait one frame for slaves to catch up
                        '''
                        waiting_to_start = False
            except IOError:
                print("Timeout")
                

    print("Starting game!")

    random.seed()

    while running:
        # Start new match
        print("Starting new match...")
        # Set up cards
        remaining_numbers = []
        for i in range(0,15):
            remaining_numbers.append(i)
        # Reset player hands
        hand_p1 = [-1] * 4
        hand_p2 = [-1] * 4
        # Reset rounds played
        rounds_played = 0
        round_status = NONE
        score_p1 = 0
        score_p2 = 0
        # Let slaves know new round will begin
        start_match_packet_p1 = [0x03] * 5
        start_match_packet_p1[1] = get_new_card(remaining_numbers)
        start_match_packet_p1[2] = get_new_card(remaining_numbers)
        start_match_packet_p1[3] = get_new_card(remaining_numbers)
        start_match_packet_p1[4] = get_new_card(remaining_numbers)

        hand_p1[UP] = start_match_packet_p1[1]
        hand_p1[LEFT] = start_match_packet_p1[2]
        hand_p1[DOWN] = start_match_packet_p1[3]
        hand_p1[RIGHT] = start_match_packet_p1[4]

        start_match_packet_p2 = [0x04] * 5
        start_match_packet_p2[1] = get_new_card(remaining_numbers)
        start_match_packet_p2[2] = get_new_card(remaining_numbers)
        start_match_packet_p2[3] = get_new_card(remaining_numbers)
        start_match_packet_p2[4] = get_new_card(remaining_numbers)

        hand_p2[UP] = start_match_packet_p2[1]
        hand_p2[LEFT] = start_match_packet_p2[2]
        hand_p2[DOWN] = start_match_packet_p2[3]
        hand_p2[RIGHT] = start_match_packet_p2[4]

        sent_packet = False
        while not sent_packet:
            try:
                print(start_match_packet_p2)
                bus.write_i2c_block_data(0, 1, start_match_packet_p1)
                time.sleep(0.1)
                bus.write_i2c_block_data(0, 1, start_match_packet_p2)
                time.sleep(0.02)
                # Send twice to make sure they get it!
                bus.write_i2c_block_data(0, 1, start_match_packet_p1)
                time.sleep(0.1)
                bus.write_i2c_block_data(0, 1, start_match_packet_p2)
                time.sleep(0.02)
                sent_packet = True
            except IOError:
                print("Timeout 1")
        #time.sleep(9)
        print("New match has started!")
        # Slaves are aware that match has begun
        # Receive IMU packets and process them
        while rounds_played < 8:
            # Reset player selections
            hand_select_p1 = NONE
            hand_select_p2 = NONE
            stat_select_p1 = NONE
            stat_select_p2 = NONE
            # Reset round status
            round_status = NONE
            # Start timing round
            start_time = time.time()
            target_time = start_time + ROUND_TIME
            # Begin new round!
            while (time.time() < target_time and running):
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                    elif event.type == pygame.KEYDOWN:
                        if event.key == K_ESCAPE:
                            print("Bye")
                            running = False
                got_imu_data = False
                try:
                    data_ac = bus.read_i2c_block_data(MBED_ADDRESS_AC, 1, 2)
                    data_d  = bus.read_i2c_block_data(MBED_ADDRESS_D,  1, 2)
                    imu_data = data_ac + data_d
                    imu_packet = [0x01] * 5
                    imu_packet[1] = imu_data[0]
                    imu_packet[2] = imu_data[1]
                    imu_packet[3] = imu_data[2]
                    imu_packet[4] = imu_data[3]
                    time.sleep(0.02)
                    #print("Stuff:")
                    #print(data_ac)
                    #print(data_d)
                    print(imu_packet)
                    bus.write_i2c_block_data(0, 1, imu_packet)
                    got_imu_data = True
                except IOError:
                    print("Timeout 2")

                if got_imu_data:
                    # Read IMU data - A1
                    imu_byte = imu_data[0]
                    imu_bits = (imu_byte & 0b11100000) >> 5
                    if (imu_bits == 0 or imu_bits == 4):
                        v_a1_tilt = V_NO_TILT
                    elif (imu_bits == 3):
                        v_a1_tilt = V_DOWN_TILT_STRONG
                    elif (imu_bits == 7):
                        v_a1_tilt = V_UP_TILT_STRONG

                    imu_bits = (imu_byte & 0b00011100) >> 2
                    if (imu_bits == 0 or imu_bits == 4):
                        h_a1_tilt = H_NO_TILT
                    elif (imu_bits == 3):
                        h_a1_tilt = H_RIGHT_TILT_STRONG
                    elif (imu_bits == 7):
                        h_a1_tilt = H_LEFT_TILT_STRONG

                    imu_bits = (imu_byte & 0b00000010)
                    if imu_bits:
                        s_a1 = S_SHAKE
                    else:
                        s_a1 = S_NO_SHAKE

                    # Read IMU data - A2
                    imu_byte = imu_data[1]
                    imu_bits = (imu_byte & 0b11100000) >> 5
                    if (imu_bits == 0 or imu_bits == 4):
                        v_a2_tilt = V_NO_TILT
                    elif (imu_bits == 3):
                        v_a2_tilt = V_DOWN_TILT_STRONG
                    elif (imu_bits == 7):
                        v_a2_tilt = V_UP_TILT_STRONG

                    imu_bits = (imu_byte & 0b00011100) >> 2
                    if (imu_bits == 0 or imu_bits == 4):
                        h_a2_tilt = H_NO_TILT
                    elif (imu_bits == 3):
                        h_a2_tilt = H_RIGHT_TILT_STRONG
                    elif (imu_bits == 7):
                        h_a2_tilt = H_LEFT_TILT_STRONG

                    imu_bits = (imu_byte & 0b00000010)
                    if imu_bits:
                        s_a2 = S_SHAKE
                    else:
                        s_a2 = S_NO_SHAKE

                    # Read IMU data - C1
                    imu_byte = imu_data[2]
                    imu_bits = (imu_byte & 0b11100000) >> 5
                    if (imu_bits == 0 or imu_bits == 4):
                        v_c1_tilt = V_NO_TILT
                    elif (imu_bits == 3):
                        v_c1_tilt = V_DOWN_TILT_STRONG
                    elif (imu_bits == 7):
                        v_c1_tilt = V_UP_TILT_STRONG

                    imu_bits = (imu_byte & 0b00011100) >> 2
                    if (imu_bits == 0 or imu_bits == 4):
                        h_c1_tilt = H_NO_TILT
                    elif (imu_bits == 3):
                        h_c1_tilt = H_RIGHT_TILT_STRONG
                    elif (imu_bits == 7):
                        h_c1_tilt = H_LEFT_TILT_STRONG

                    imu_bits = (imu_byte & 0b00000010)
                    if imu_bits:
                        s_c1 = S_SHAKE
                    else:
                        s_c1 = S_NO_SHAKE

                    # Read IMU data - C2
                    imu_byte = imu_data[3]
                    imu_bits = (imu_byte & 0b11100000) >> 5
                    if (imu_bits == 0 or imu_bits == 4):
                        v_c2_tilt = V_NO_TILT
                    elif (imu_bits == 3):
                        v_c2_tilt = V_DOWN_TILT_STRONG
                    elif (imu_bits == 7):
                        v_c2_tilt = V_UP_TILT_STRONG

                    imu_bits = (imu_byte & 0b00011100) >> 2
                    if (imu_bits == 0 or imu_bits == 4):
                        h_c2_tilt = H_NO_TILT
                    elif (imu_bits == 3):
                        h_c2_tilt = H_RIGHT_TILT_STRONG
                    elif (imu_bits == 7):
                        h_c2_tilt = H_LEFT_TILT_STRONG

                    imu_bits = (imu_byte & 0b00000010)
                    if imu_bits:
                        s_c2 = S_SHAKE
                    else:
                        s_c2 = S_NO_SHAKE

                    # Translate IMU data to player selections

                    # P1 left hand
                    if v_a1_tilt == V_DOWN_TILT_STRONG:
                        hand_select_p1 = DOWN
                    elif v_a1_tilt == V_UP_TILT_STRONG:
                        hand_select_p1 = UP
                    elif h_a1_tilt == H_LEFT_TILT_STRONG:
                        hand_select_p1 = LEFT
                    elif h_a1_tilt == H_RIGHT_TILT_STRONG:
                        hand_select_p1 = RIGHT
                        
                    # P1 right hand
                    if v_a2_tilt == V_DOWN_TILT_STRONG:
                        stat_select_p1 = DOWN
                    elif v_a2_tilt == V_UP_TILT_STRONG:
                        stat_select_p1 = UP
                    elif h_a2_tilt == H_LEFT_TILT_STRONG:
                        stat_select_p1 = LEFT
                    elif h_a2_tilt == H_RIGHT_TILT_STRONG:
                        stat_select_p1 = RIGHT


                    # P2 left hand
                    if v_c1_tilt == V_DOWN_TILT_STRONG:
                        hand_select_p2 = DOWN
                    elif v_c1_tilt == V_UP_TILT_STRONG:
                        hand_select_p2 = UP
                    elif h_c1_tilt == H_LEFT_TILT_STRONG:
                        hand_select_p2 = LEFT
                    elif h_c1_tilt == H_RIGHT_TILT_STRONG:
                        hand_select_p2 = RIGHT
                        
                    # P2 right hand
                    if v_c2_tilt == V_DOWN_TILT_STRONG:
                        stat_select_p2 = DOWN
                    elif v_c2_tilt == V_UP_TILT_STRONG:
                        stat_select_p2 = UP
                    elif h_c2_tilt == H_LEFT_TILT_STRONG:
                        stat_select_p2 = LEFT
                    elif h_c2_tilt == H_RIGHT_TILT_STRONG:
                        stat_select_p2 = RIGHT

                end_time = time.time()
                deltatime = end_time - start_time
                if (deltatime > ROUND_TIME):
                    deltatime = ROUND_TIME
                label_time = font.render("Time passed: %3.2f" % (deltatime), 1, (0,0,0), (255,255,255))

                screen.fill((128, 128, 128))

                screen.blit(label_time, (50, 50))
                pygame.display.flip()

            # FOR TEST PURPOSES
            #hand_select_p1 = 1
            #stat_select_p1 = 1
            #hand_select_p2 = 1
            #stat_select_p2 = 2

            # End of round, see if inputs are valid
            if (hand_select_p1 != NONE and stat_select_p1 != NONE and hand_select_p2 != NONE and stat_select_p2 != NONE):
                card_p1 = hand_p1[hand_select_p1]
                card_p2 = hand_p2[hand_select_p2]
                # Check if players selected empty cards
                if (card_p1 != NONE and card_p2 != NONE and card_p1 != 0xFF and card_p2 != 0xFF):
                    # If we get here, round is good and round_status is set to sth that is not NONE
                    real_card_p1 = lookup_card(card_p1)
                    real_card_p2 = lookup_card(card_p2)
                    if (stat_select_p1 == stat_select_p2):
                        stat_p1 = real_card_p1[stat_select_p1+1]
                        stat_p2 = real_card_p2[stat_select_p2+1]
                    else:
                        stat_p1 = real_card_p1[stat_select_p1+1] + real_card_p1[stat_select_p2+1]
                        stat_p2 = real_card_p2[stat_select_p1+1] + real_card_p2[stat_select_p2+1]
                    if (stat_p1 > stat_p2):
                        round_status = P1_WON
                    elif (stat_p2 > stat_p1):
                        round_status = P2_WON
                    else:
                        round_status = TIE
                    rounds_played += 1

            if (round_status == NONE):
                # players screwed up input, so communicate that
                print("Bad input! Re-trying round...")
                bad_input_packet = [0x07]
                sent_packet = False
                while not sent_packet:
                    try:
                        data_slave = bus.write_i2c_block_data(0, 1, bad_input_packet)
                        time.sleep(0.02)
                        data_slave = bus.write_i2c_block_data(0, 1, bad_input_packet)
                        sent_packet = True
                    except IOError:
                        print("Timeout bad input")
                # Draw bad input warning
                label_msg = font.render("Invalid inputs! Let's retry this round...", 1, (0,0,0), (255,255,255))
                start_time = time.time()
                target_time = start_time + MSG_TIME
                while (time.time() < target_time):
                    screen.fill((128, 128, 128))

                    screen.blit(label_msg, (550, 550))
                    pygame.display.flip()
            else:
                # good round, send that to players
		old_card_p1 = card_p1
		old_card_p2 = card_p2
                # fetch new cards, if possible
                if (len(remaining_numbers) > 1):
                    new_card_p1 = get_new_card(remaining_numbers)
                    new_card_p2 = get_new_card(remaining_numbers)
                else:
                    new_card_p1 = 0xFF
                    new_card_p2 = 0xFF

                hand_p1[hand_select_p1] = new_card_p1
                hand_p2[hand_select_p2] = new_card_p2

                end_round_packet_p1 = [0x05] * 4
                end_round_packet_p1[1] = new_card_p1
                end_round_packet_p1[2] = hand_select_p1
                end_round_packet_p1[3] = round_status

                end_round_packet_p2 = [0x06] * 4
                end_round_packet_p2[1] = new_card_p2
                end_round_packet_p2[2] = hand_select_p2
                end_round_packet_p2[3] = round_status

                sent_packet = False
                while not sent_packet:
                    try:
                        data_slave = bus.write_i2c_block_data(0, 1, end_round_packet_p1)
                        time.sleep(0.1)
                        data_slave = bus.write_i2c_block_data(0, 1, end_round_packet_p2)
                        time.sleep(0.1)
                        data_slave = bus.write_i2c_block_data(0, 1, end_round_packet_p1)
                        time.sleep(0.1)
                        data_slave = bus.write_i2c_block_data(0, 1, end_round_packet_p2)
                        sent_packet = True
                    except IOError:
                        print("Timeout round end")
                # Draw player choices
                label_msg_1 = midfont.render("Player 1 picked the card %s" % real_card_p1[0], 1, (0,0,0), (255,255,255))
                label_msg_2 = midfont.render("and the stat %s." % int_to_stat(stat_select_p1), 1, (0,0,0), (255,255,255))
                label_msg_3 = midfont.render("Player 2 picked the card %s" % real_card_p2[0], 1, (0,0,0), (255,255,255))
                label_msg_4 = midfont.render("and the stat %s." % int_to_stat(stat_select_p2), 1, (0,0,0), (255,255,255))
                label_msg_5 = midfont.render("%s's stats add up to %d." % (real_card_p1[0], stat_p1), 1, (0,0,0), (255,255,255))
                label_msg_6 = midfont.render("%s's stats add up to %d." % (real_card_p2[0], stat_p2), 1, (0,0,0), (255,255,255))
                if (round_status == TIE):
                    label_msg_7 = font.render("It's a tie!", 1, (0,0,0), (255,255,255))
                elif (round_status == P1_WON):
                    label_msg_7 = font.render("Player 1 wins!", 1, (0,0,0), (255,255,255))
                elif (round_status == P2_WON):
                    label_msg_7 = font.render("Player 2 wins!", 1, (0,0,0), (255,255,255))
                else:
                    label_msg_7 = font.render("", 1, (0,0,0), (255,255,255))
                start_time = time.time()
                target_time = start_time + MSG_TIME / 4.0
                screen.fill((128, 128, 128))
                screen.blit(label_msg_1, (50, 20))
                screen.blit(label_msg_2, (50, 70))
                screen.blit(label_msg_3, (1250, 20))
                screen.blit(label_msg_4, (1250, 70))

                pygame.display.flip()
                while (time.time() < target_time):
                    pass
                
                target_time = start_time + MSG_TIME / 2.0
                draw_card(old_card_p1, 50, 120)
                draw_card(old_card_p2, 1250, 120)            
                screen.blit(label_msg_5, (50, 770))
                screen.blit(label_msg_6, (1250, 770))
                pygame.display.flip()
                while (time.time() < target_time):
                    pass
                
                target_time = start_time + 20.0
                screen.blit(label_msg_7, (600, 520))
                pygame.display.flip()

                while (time.time() < target_time):
                    pass

                # Draw prompt for player 1 to roll
                label_msg = font.render("Player 1, roll a die! (Shake one arm)", 1, (0, 0, 0), (255, 255, 255))
                # roll die for player 1 
                s_a1 = S_NO_SHAKE
                s_a2 = S_NO_SHAKE
                while (s_a1 == S_NO_SHAKE and s_a2 == S_NO_SHAKE):
                    for event in pygame.event.get():
                        if event.type == pygame.QUIT:
                            running = False
                        elif event.type == pygame.KEYDOWN:
                            if event.key == K_ESCAPE:
                                print("Bye")
                                running = False
                    try:
                        data_ac = bus.read_i2c_block_data(MBED_ADDRESS_AC, 1, 2)
                        time.sleep(0.02)
                        data_d  = bus.read_i2c_block_data(MBED_ADDRESS_D,  1, 2)
                        imu_data = data_ac + data_d
                        #print(imu_data)
                        imu_packet = [0x01] * 5
                        imu_packet[1] = imu_data[0]
                        imu_packet[2] = imu_data[1]
                        imu_packet[3] = imu_data[2]
                        imu_packet[4] = imu_data[3]
                        time.sleep(0.02)
                        bus.write_i2c_block_data(0, 1, imu_packet)
                    except IOError:
                        print("Timeout P1 shake")

                    # Read IMU data - A1
                    imu_byte = imu_data[0]
                    imu_bits = (imu_byte & 0b11100000) >> 5
                    if (imu_bits == 0 or imu_bits == 4):
                        v_a1_tilt = V_NO_TILT
                    elif (imu_bits == 3):
                        v_a1_tilt = V_DOWN_TILT_STRONG
                    elif (imu_bits == 7):
                        v_a1_tilt = V_UP_TILT_STRONG

                    imu_bits = (imu_byte & 0b00011100) >> 2
                    if (imu_bits == 0 or imu_bits == 4):
                        h_a1_tilt = H_NO_TILT
                    elif (imu_bits == 3):
                        h_a1_tilt = H_RIGHT_TILT_STRONG
                    elif (imu_bits == 7):
                        h_a1_tilt = H_LEFT_TILT_STRONG

                    imu_bits = (imu_byte & 0b00000010)
                    if imu_bits:
                        s_a1 = S_SHAKE
                    else:
                        s_a1 = S_NO_SHAKE

                    # Read IMU data - A2
                    imu_byte = imu_data[1]
                    imu_bits = (imu_byte & 0b11100000) >> 5
                    if (imu_bits == 0 or imu_bits == 4):
                        v_a2_tilt = V_NO_TILT
                    elif (imu_bits == 3):
                        v_a2_tilt = V_DOWN_TILT_STRONG
                    elif (imu_bits == 7):
                        v_a2_tilt = V_UP_TILT_STRONG

                    imu_bits = (imu_byte & 0b00011100) >> 2
                    if (imu_bits == 0 or imu_bits == 4):
                        h_a2_tilt = H_NO_TILT
                    elif (imu_bits == 3):
                        h_a2_tilt = H_RIGHT_TILT_STRONG
                    elif (imu_bits == 7):
                        h_a2_tilt = H_LEFT_TILT_STRONG

                    imu_bits = (imu_byte & 0b00000010)
                    if imu_bits:
                        s_a2 = S_SHAKE
                    else:
                        s_a2 = S_NO_SHAKE

                    if (round_status == P1_WON):
                        roll = random.randint(3,6)
                    else:
                        roll = random.randint(1,4)
                    number_msg = font.render("%d" % roll, 1, (0, 0, 0), (255, 255, 255))

                    screen.fill((128, 128, 128))
                    screen.blit(label_msg, (600, 200))
                    screen.blit(number_msg, (950, 600))
                    pygame.display.flip()

                # player 1 shook hands, so throw dice
                if (round_status == P1_WON):
                    roll = random.randint(3,6)
                else:
                    roll = random.randint(1,4)
                score_p1 += roll

                label_msg = font.render("Player 1 rolled %d! Your score is now %d" % (roll, score_p1), 1, (0, 0, 0), (255, 255, 255))
                number_msg = font.render("%d" % roll, 1, (0, 0, 0), (255, 255, 255))

                screen.fill((128, 128, 128))
                screen.blit(label_msg, (200, 200))
                screen.blit(number_msg, (950, 600))
                pygame.display.flip()

                start_time = time.time()
                target_time = start_time + MSG_TIME
                while (time.time() < target_time):
                    pass
                
                # Draw prompt for player 2 to roll
                label_msg = font.render("Player 2, roll a die! (Shake one arm)", 1, (0, 0, 0), (255, 255, 255))
                # roll die for player 2
                s_c1 = S_NO_SHAKE
                s_c2 = S_NO_SHAKE
                while (s_c1 == S_NO_SHAKE and s_c2 == S_NO_SHAKE):
                    for event in pygame.event.get():
                        if event.type == pygame.QUIT:
                            running = False
                        elif event.type == pygame.KEYDOWN:
                            if event.key == K_ESCAPE:
                                print("Bye")
                                running = False
                    try:
                        data_ac = bus.read_i2c_block_data(MBED_ADDRESS_AC, 1, 2)
                        time.sleep(0.02)
                        data_d  = bus.read_i2c_block_data(MBED_ADDRESS_D,  1, 2)
                        imu_data = data_ac + data_d
                        #print(imu_data)
                        imu_packet = [0x01] * 5
                        imu_packet[1] = imu_data[0]
                        imu_packet[2] = imu_data[1]
                        imu_packet[3] = imu_data[2]
                        imu_packet[4] = imu_data[3]
                        time.sleep(0.02)
                        bus.write_i2c_block_data(0, 1, imu_packet)
                    except IOError:
                        print("Timeout P2 shake")
                        
                    # Read IMU data - C1
                    imu_byte = imu_data[2]
                    imu_bits = (imu_byte & 0b11100000) >> 5
                    if (imu_bits == 0 or imu_bits == 4):
                        v_c1_tilt = V_NO_TILT
                    elif (imu_bits == 3):
                        v_c1_tilt = V_DOWN_TILT_STRONG
                    elif (imu_bits == 7):
                        v_c1_tilt = V_UP_TILT_STRONG

                    imu_bits = (imu_byte & 0b00011100) >> 2
                    if (imu_bits == 0 or imu_bits == 4):
                        h_c1_tilt = H_NO_TILT
                    elif (imu_bits == 3):
                        h_c1_tilt = H_RIGHT_TILT_STRONG
                    elif (imu_bits == 7):
                        h_c1_tilt = H_LEFT_TILT_STRONG

                    imu_bits = (imu_byte & 0b00000010)
                    if imu_bits:
                        s_c1 = S_SHAKE
                    else:
                        s_c1 = S_NO_SHAKE

                    # Read IMU data - C2
                    imu_byte = imu_data[3]
                    imu_bits = (imu_byte & 0b11100000) >> 5
                    if (imu_bits == 0 or imu_bits == 4):
                        v_c2_tilt = V_NO_TILT
                    elif (imu_bits == 3):
                        v_c2_tilt = V_DOWN_TILT_STRONG
                    elif (imu_bits == 7):
                        v_c2_tilt = V_UP_TILT_STRONG

                    imu_bits = (imu_byte & 0b00011100) >> 2
                    if (imu_bits == 0 or imu_bits == 4):
                        h_c2_tilt = H_NO_TILT
                    elif (imu_bits == 3):
                        h_c2_tilt = H_RIGHT_TILT_STRONG
                    elif (imu_bits == 7):
                        h_c2_tilt = H_LEFT_TILT_STRONG

                    imu_bits = (imu_byte & 0b00000010)
                    if imu_bits:
                        s_c2 = S_SHAKE
                    else:
                        s_c2 = S_NO_SHAKE

                    if (round_status == P2_WON):
                        roll = random.randint(3,6)
                    else:
                        roll = random.randint(1,4)
                    
                    number_msg = font.render("%d" % roll, 1, (0, 0, 0), (255, 255, 255))

                    screen.fill((128, 128, 128))
                    screen.blit(label_msg, (600, 200))
                    screen.blit(number_msg, (950, 600))
                    pygame.display.flip()

                # player 2 shook hands, so throw dice
                if (round_status == P2_WON):
                    roll = random.randint(3,6)
                else:
                    roll = random.randint(1,4)
                score_p2 += roll

                label_msg = font.render("Player 2 rolled %d! Your score is now %d" % (roll, score_p2), 1, (0, 0, 0), (255, 255, 255))
                number_msg = font.render("%d" % roll, 1, (0, 0, 0), (255, 255, 255))

                screen.fill((128, 128, 128))
                screen.blit(label_msg, (200, 200))
                screen.blit(number_msg, (950, 600))
                pygame.display.flip()

                start_time = time.time()
                target_time = start_time + MSG_TIME
                while (time.time() < target_time):
                    pass


                # Start new round, communicate that to players
                begin_new_round_packet = [0x08]
                sent_packet = False
                while not sent_packet:
                    try:
                        data_slave = bus.write_i2c_block_data(0, 1, begin_new_round_packet)
                        time.sleep(0.02)
                        data_slave = bus.write_i2c_block_data(0, 1, begin_new_round_packet)
                        sent_packet = True
                    except IOError:
                        print("Timeout begin new round")
