import pygame
import smbus
from pygame.locals import *

bus = smbus.SMBus(1)
ENABLE_I2C = True
MBED_ADDRESS_SLAVE = 0x07   # this is for the slave Pi


PLAYER1 = 1
PLAYER2 = 2
player = PLAYER1
prevWinner = 0

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

UP = 0
LEFT = 1
RIGHT = 2
DOWN = 3

S_NO_SHAKE = 0
S_SHAKE = 1

h_a1_tilt = H_NO_TILT
h_a2_tilt = H_NO_TILT

v_a1_tilt = V_NO_TILT
v_a2_tilt = V_NO_TILT

s_a1 = S_NO_SHAKE
s_a2 = S_NO_SHAKE

h_c1_tilt = H_NO_TILT
h_c2_tilt = H_NO_TILT

v_c1_tilt = V_NO_TILT
v_c2_tilt = V_NO_TILT

s_c1 = S_NO_SHAKE
s_c2 = S_NO_SHAKE

hand_select_p1 = 0
hand_select_p2 = 0
stat_select_p1 = 0
stat_select_p2 = 0


#You hand, in order: top, left, right, bottom
curr_deck = [0, 0, 0, 0]

#Divide by 4 to get the card position, %4 for stat
curr_selection = 0

#Put in the "enum"
RGB_encoding = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
#Set up window
(width, height) = (1600, 900)#(1920, 1023)
screen = pygame.display.set_mode((width, height),pygame.NOFRAME)
#initialize modules
pygame.init()
#initialize fonts
namefont = pygame.font.SysFont("comicsansms", 100)
statfont = pygame.font.SysFont("comicsansms", 50)

#runtime booleans
running = True
waiting_to_start = True
between_turns = True

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


def draw_card(value, position):
    global curr_selection
    print("CURRPOSS:%i" % curr_selection)
    #Offsets from positions of top card
    x_pos = 7*width/16
    y_offset = 0
    if position == 1:
        x_pos = width/8
        y_offset = height/4
    if position == 2:
        x_pos = 3*width/4
        y_offset = height/4
    if position == 3:
        y_offset = height/2
        
    #No card
    if value == 255:
	pygame.draw.rect(screen, (123, 123, 123), Rect(x_pos-120, y_offset+20, 350, 450))
        return
    else:
        stats = lookup_card(value)
    name = namefont.render(stats[0], 1, (0,0,0), RGB_encoding[position])
    highlightedRow = (curr_selection / 4 == position)
    
    highlighted = highlightedRow & (curr_selection % 4 == 0)
    speed = statfont.render("Speed: %i" % stats[1], 1, (0,0,0), (255-123*highlighted, 255-123*highlighted, 255-123*highlighted))

    highlighted = highlightedRow & (curr_selection % 4 == 1)
    fierceness = statfont.render("Fierceness: %i" % stats[2], 1, (0,0,0), (255-123*highlighted, 255-123*highlighted, 255-123*highlighted))

    highlighted = highlightedRow & (curr_selection % 4 == 2)
    intelligence = statfont.render("Intelligence: %i" % stats[3], 1, (0,0,0), (255-123*highlighted, 255-123*highlighted, 255-123*highlighted))

    highlighted = highlightedRow & (curr_selection % 4 == 3)
    cuteness = statfont.render("Cuteness: %i" % stats[4], 1, (0,0,0), (255-123*highlighted, 255-123*highlighted, 255-123*highlighted))
    
    screen.blit(name, (x_pos, 45+y_offset))
    screen.blit(speed, (x_pos, 125+y_offset))
    screen.blit(fierceness, (x_pos-180, 200+y_offset))
    screen.blit(intelligence, (x_pos+120, 200+y_offset))
    screen.blit(cuteness, (x_pos-20, 300+y_offset))

def wait_for_next_round(winner):
    wait_text = statfont.render("You lost...", 1, (0,0,0))
    if player == winner:
        wait_text = statfont.render("You won!", 1, (0,0,0))
    elif winner == 0:
        wait_text = statfont.render("You tied.", 1, (0,0,0))
    screen.blit(wait_text, (width/2-80, height/2-80))
    screen.blit(statfont.render("Look at center screen!", 1, (0,0,0)), (width/2-200, height/2-40))
      
def interpret_IMU(imu_data):
    global v_a1_tilt
    global h_a1_tilt
    global v_a2_tilt
    global h_a2_tilt
    global s_a1
    global s_a2
    global v_c1_tilt
    global h_c1_tilt
    global v_c2_tilt
    global h_c2_tilt
    global s_c1
    global s_c2
    global hand_select_p1
    global stat_select_p1
    global hand_select_p2
    global stat_select_p2
    global curr_selection
    
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

    if player == PLAYER1:
        for i in range(0,4):
            for j in range(0,4):
                if i == hand_select_p1 and j == stat_select_p1:
                    curr_selection = i*4 + j
    if player == PLAYER2:
        for i in range(0,4):
            for j in range(0,4):
                if i == hand_select_p2 and j == stat_select_p2:
                    curr_selection = i*4 + j
                    
def interpret_data(data_received):
    global between_turns, prevWinner, waiting_to_start
    data_slave = data_received[1:6]
    if data_slave[0] == 1:
        interpret_IMU(data_slave[1:5])
    elif data_slave[0] == 3 and player == PLAYER1:
        waiting_to_start = False
        between_turns = False
        for i in range(0,4):
            curr_deck[i] = data_slave[i+1]
    elif data_slave[0] == 4 and player == PLAYER2:
        waiting_to_start = False
        between_turns = False
        for i in range(0,4):
            curr_deck[i] = data_slave[i+1]  
    elif data_slave[0] == 5 and player == PLAYER1:
        curr_deck[data_slave[2]] = data_slave[1]
        prevWinner = data_slave[3]
        between_turns = True
        wait_for_next_round(data_slave[3])
    elif data_slave[0] == 6 and player == PLAYER2:
        print(data_slave)
        curr_deck[data_slave[2]] = data_slave[1]
        prevWinner = data_slave[3]
        between_turns = True
        wait_for_next_round(data_slave[3])
    elif data_slave[0] == 7 or data_slave[0] == 8:
        between_turns = False
        

screen.fill((255,255,255))

while running:
    global waiting_to_start
    pygame.display.flip()
    while waiting_to_start:
        if (ENABLE_I2C):
            try:
                interpret_data(bus.read_i2c_block_data(MBED_ADDRESS_SLAVE, 1, 6))
                print ("%i" % waiting_to_start)
            except IOError:
                print("Timeout while waiting")
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == K_ESCAPE:
                print("User exited")
                running = False 
    if (ENABLE_I2C):
        try:
            interpret_data(bus.read_i2c_block_data(MBED_ADDRESS_SLAVE, 1, 6))
            print ("Should be zero: %i" % waiting_to_start)
        except IOError:
            print("Timeout during my move")            
   # print "Selection is %i" % curr_selection 
    screen.fill((255,255,255))
    for i in range(0,4):
        draw_card(curr_deck[i],i)
    if (between_turns):
        wait_for_next_round(prevWinner)
    
