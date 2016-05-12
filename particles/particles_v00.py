from __future__ import print_function
import time
import pygame
import smbus
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

# python 2 has no enums, lol
TEAM_1 = 1
TEAM_2 = 2
BOARD1_X = 0
BOARD1_Y = 1
BOARD2_X = 2
BOARD2_Y = 3

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
imu_packet = [0x00]*5
imu_packet[0] = 0x01 # set first byte to 0x01

ENABLE_I2C = True

# i2c things
MBED_ADDRESS_AC = 0x07  # these two
MBED_ADDRESS_D  = 0x08  # are for the master Pi
 
MBED_ADDRESS_SLAVE = 0x07   # this is for the slave Pi

SYNC_COUNTER_MAX = 10
sync_counter = 0
test_data = bytes([0xAB, 0xCD, 0xEF, 0x00, 0x00, 0x99, 0x99])

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
font = pygame.font.SysFont("comicsansms", 35)
#render text as a surface and add to screen
attract1 = True
attract2 = True
label1 = font.render("", 1, (0,0,0), (255*(not attract1),255*attract1,0))
label2 = font.render("", 1, (0,0,0), (255*(not attract2),255*attract2,0))

#initialize keyboard

env = PyParticlesFrameRate.Environment((width, height))

#-1, 0, or 1 for decrease, stagnate, or increase mass, respectively
mass1 = 0
mass2 = 0
#0 or 1 for whether power-up is active
item1 = False
item2 = False


#env.addParticles(5, mass=particleMass, team=TEAM_1)
env.addParticle(x=int(width / 12.0), y=int(height * 1.0 / 4.0), team=TEAM_1)
env.addParticle(x=int(width / 12.0), y=int(height * 2.0 / 4.0), team=TEAM_1)
env.addParticle(x=int(width / 12.0), y=int(height * 3.0 / 4.0), team=TEAM_1)

env.addParticle(x=int(width /  4.0), y=int(height * 1.0 / 3.0), team=TEAM_1)
env.addParticle(x=int(width /  4.0), y=int(height * 2.0 / 3.0), team=TEAM_1)
#env.addParticles(5, mass=particleMass,colour=(240, 240, 240), team=TEAM_2)
env.addParticle(x=int(width * 11.0 / 12.0), y=int(height * 1.0 / 4.0), team=TEAM_2)
env.addParticle(x=int(width * 11.0 / 12.0), y=int(height * 2.0 / 4.0), team=TEAM_2)
env.addParticle(x=int(width * 11.0 / 12.0), y=int(height * 3.0 / 4.0), team=TEAM_2)

env.addParticle(x=int(width *  9.0 / 12.0), y=int(height * 1.0 / 3.0), team=TEAM_2)
env.addParticle(x=int(width *  9.0 / 12.0), y=int(height * 2.0 / 3.0), team=TEAM_2)

#env.addBoards(x=450,y=100,n=len(boardpos),width=10,height=50, boardnum=0)
env.addBoard(x= int(width / 6.0), y=100, team=TEAM_1)
env.addBoard(x= int(width * 5.0 / 6.0), y=100, team=TEAM_2)

GOAL_LINE_WIDTH = 20

# rectangles showing goal lines
rect_goal_1 = Rect(0, int(height / 5.0), GOAL_LINE_WIDTH, int(height * 3.0 / 5.0))
rect_goal_2 = Rect(width - GOAL_LINE_WIDTH, int(height / 5.0), GOAL_LINE_WIDTH, int(height * 3.0 / 5.0))

#Observed FPS, and the FPS as a percentage of ideal FPS / realFPS
realFPS = 25
percentFPS = 1

#array for particle mass
keys = [0,0]
#Tuples, with first value -1 left, 1 right; second value -1 for up, 1 for down
boardMoves = [0, 0, 0, 0]

selected_particle = None
running = True

#clock.tick_busy_loop(25)

while running:
    waiting_to_start = True
    while waiting_to_start:
        screen.fill(env.colour)
    
        pygame.draw.rect(screen, (0, 0, 0), rect_goal_1)
        pygame.draw.rect(screen, (255, 255, 255), rect_goal_2)
        
        # To achieve "shifted screen" effect, just shift everything when drawing it.
        for p in env.particles:
            pygame.draw.circle(screen, p.colour, (int(p.x) - WIDTH_OFFSET, int(p.y)), p.size, p.thickness)
            
        for b in env.boards:
            pygame.draw.circle(screen, b.colour, (int(b.x) - WIDTH_OFFSET, int(b.y)), b.size)

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
                        start_byte = [0x03]
                        bus.write_i2c_block_data(0, 1, start_byte) # must send to address 0 = "write general"
                        #clock.tick_busy_loop(25) # wait one frame for slaves to catch up
                        waiting_to_start = False
            except IOError:
                print("Timeout 1")
                

    print("Starting game!")

    while running:
        start_time = time.time()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            #Player 2 attraction / repulsion
            elif event.type == pygame.MOUSEBUTTONDOWN:
                attract1 = not attract1
            elif event.type == pygame.KEYDOWN:
                #Player 2 attraction / repulsion
                if event.key == K_SPACE:
                    attract2 = not attract2
                #Player 1 item use
                if event.key == K_p:
                    item1 = not item1
                #Player 1 mass decreases and increases
                if event.key == K_a:           
                    if mass1:
                        mass1 = 0
                    else:
                        mass1 = -1
                if event.key == K_d:
                    if mass1:
                        mass1 = 0
                    else:
                        mass1 = 1
                #Player 1 board y-movement
                if event.key == K_w:
                    if boardMoves[BOARD1_Y]:
                        boardMoves[BOARD1_Y] = 0
                    else:
                        boardMoves[BOARD1_Y]= -1
                if event.key == K_s:
                    if boardMoves[BOARD1_Y]:
                        boardMoves[BOARD1_Y] = 0
                    else:
                        boardMoves[BOARD1_Y] = 1
                #Player 1 board x-movement
                if event.key == K_c:
                    if boardMoves[BOARD1_X]:
                        boardMoves[BOARD1_X] = 0
                    else:
                        boardMoves[BOARD1_X] = -1
                if event.key == K_v:
                    if boardMoves[BOARD1_X]:
                        boardMoves[BOARD1_X] = 0
                    else:
                        boardMoves[BOARD1_X] = 1
                #Quit
                if event.key == K_ESCAPE:
                    print("Bye")
                    running = False
                   
           #    (mouseX, mouseY) = pygame.mouse.get_pos()
           #    selected_particle = env.findParticle(mouseX, mouseY)
           #elif event.type == pygame.MOUSEBUTTONUP:
           #    selected_particle = None

        label1 = font.render("Score: %i, Mass: %i, Item: %d, ItemUse: %i" % (env.score_1, env.curr_mass1, env.item1_wait_count, item1), 1, (0,0,0), (255*(not attract1),255*attract1,0))
        label2 = font.render("Score: %i, Mass: %i, Item: %d, ItemUse: %i" % (env.score_2, env.curr_mass2, env.item2_wait_count, item2), 1, (0,0,0), (255*(not attract2),255*attract2,0))
                
       #if selected_particle:
       #    (mouseX, mouseY) = pygame.mouse.get_pos()
       #    selected_particle.mouseMove(mouseX, mouseY)

    ########## BEGIN IMU SHENANIGANS ##########################################

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

        # Translate IMU data to game flags! #############################
        # Handle attract/repulsion (shaking) #######################
        if (s_a1 == S_SHAKE and s_a2 == S_NO_SHAKE) :
            attract1 = True
        elif (s_a1 == S_NO_SHAKE and s_a2 == S_SHAKE):
            attract1 = False
        # else, maintain value of attract1
        
        if (s_c1 == S_SHAKE and s_c2 == S_NO_SHAKE) :
            attract2 = True
        elif (s_c1 == S_NO_SHAKE and s_c2 == S_SHAKE):
            attract2 = False
        # else, maintain value of attract2

        # Handle mass (left arm horizontal tilt) ###################
        if (h_a1_tilt == H_NO_TILT):
            mass1 = 0   # keep mass
        elif (h_a1_tilt == H_LEFT_TILT_STRONG):
            mass1 = -1  # decrease mass
        elif (h_a1_tilt == H_RIGHT_TILT_STRONG):
            mass1 = 1   # increase mass

        if (h_c1_tilt == H_NO_TILT):
            mass2 = 0   # keep mass
        elif (h_c1_tilt == H_LEFT_TILT_STRONG):
            mass2 = -1  # decrease mass
        elif (h_c1_tilt == H_RIGHT_TILT_STRONG):
            mass2 = 1   # increase mass

        # Handle items (left arm vertical tilt) ####################
        print("%d" % v_a1_tilt)
        if (v_a1_tilt == V_NO_TILT):
            item1 = False   # don't activate item
        else:
            item1 = True    # activate item

        if (v_c1_tilt == V_NO_TILT):
            item2 = False   # don't activate item
        else:
            item2 = True    # activate item

        # Handle x movement of boards (right arm horizontal tilt) ##
        if (h_a2_tilt == H_NO_TILT):
            boardMoves[BOARD1_X] = 0    # stop moving board in x direction
        elif (h_a2_tilt == H_LEFT_TILT_STRONG):
            boardMoves[BOARD1_X] = -1   # move board to left
        elif (h_a2_tilt == H_RIGHT_TILT_STRONG):
            boardMoves[BOARD1_X] = 1    # move board to right

        if (h_c2_tilt == H_NO_TILT):
            boardMoves[BOARD2_X] = 0    # stop moving board in x direction
        elif (h_c2_tilt == H_LEFT_TILT_STRONG):
            boardMoves[BOARD2_X] = -1   # move board to left
        elif (h_c2_tilt == H_RIGHT_TILT_STRONG):
            boardMoves[BOARD2_X] = 1    # move board to right        

        # Handle y movement of boards (right arm vertical tilt) ####
        if (v_a2_tilt == V_NO_TILT):
            boardMoves[BOARD1_Y] = 0    # stop moving board in y direction
        elif (v_a2_tilt == V_UP_TILT_STRONG):
            boardMoves[BOARD1_Y] = -1   # move board up
        elif (v_a2_tilt == V_DOWN_TILT_STRONG):
            boardMoves[BOARD1_Y] = 1    # move board down

        if (v_c2_tilt == V_NO_TILT):
            boardMoves[BOARD2_Y] = 0    # stop moving board in y direction
        elif (v_c2_tilt == V_UP_TILT_STRONG):
            boardMoves[BOARD2_Y] = -1   # move board up
        elif (v_c2_tilt == V_DOWN_TILT_STRONG):
            boardMoves[BOARD2_Y] = 1    # move board down        

    ######################## END IMU SHENANIGANS #########################

        #Gives all particles' new positions as a percentage of fps to desired fps
        env.update(percentFPS, attract1, attract2, mass1, mass2, boardMoves, item1, item2)
        screen.fill(env.colour)
    
        pygame.draw.rect(screen, (0, 0, 0), rect_goal_1)
        pygame.draw.rect(screen, (255, 255, 255), rect_goal_2)
        
        # To achieve "shifted screen" effect, just shift everything when drawing it.
        for p in env.particles:
            pygame.draw.circle(screen, p.colour, (int(p.x) - WIDTH_OFFSET, int(p.y)), p.size, p.thickness)
            
        for b in env.boards:
            pygame.draw.circle(screen, b.colour, (int(b.x) - WIDTH_OFFSET, int(b.y)), b.size)

        screen.blit(label1, (50, 50))
        screen.blit(label2, (1300, 50))
        pygame.display.flip()

        if (ENABLE_I2C):
            try:
                if sync_counter < SYNC_COUNTER_MAX :
                    data_ac = bus.read_i2c_block_data(MBED_ADDRESS_AC, 1, 2)
                    data_d  = bus.read_i2c_block_data(MBED_ADDRESS_D,  1, 2)
                    imu_data = data_ac + data_d
                    #print(imu_data)
                else:
                    sync_counter = 0
                    bus.write_i2c_block_data(MBED_ADDRESS_AC, 1, imu_packet)
                    #print("Sent data...")
            except IOError:
                print("Timeout")
            sync_counter += 1

        clock.tick_busy_loop(20)
        realFPS = clock.get_fps()
        #Desired fps / actual fps multiplies with object speed, so they move faster at lower frame rates
        #percentFPS = 1
        #print(deltatime)
        if realFPS:
            percentFPS = 20/realFPS
       #     print(percentFPS)
        
