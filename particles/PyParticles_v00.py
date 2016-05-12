import math, random

ATTRACT_FACTOR = 40

# python 2 has no enums, lol
TEAM_1 = 1
TEAM_2 = 2
INIT_MASS1 = 100
INIT_MASS2 = 100
ITEM_USE_TIMER = 100
ITEM_WAIT_TIMER = 150
item1_wait_time = 0
item2_wait_time = 0

def addVectors((angle1, length1), (angle2, length2)):
    """ Returns the sum of two vectors """
    
    x  = math.sin(angle1) * length1 + math.sin(angle2) * length2
    y  = math.cos(angle1) * length1 + math.cos(angle2) * length2
    
    angle  = 0.5 * math.pi - math.atan2(y, x)
    length = math.hypot(x, y)

    return (angle, length)

def collide(p1, p2, fps):
    """ Tests whether two particles overlap
        If they do, make them bounce
        i.e. update their angle, speed and position """
    
    dx = p1.x - p2.x
    dy = p1.y - p2.y
    
    dist = math.hypot(dx, dy)
    if dist < p1.size + p2.size:
        if (not isinstance(p1, Board)) and (not isinstance(p2, Board)):
            returnflag = 0
            if p1.team == TEAM_1 and p2.team == TEAM_2:
                if item1_wait_time > ITEM_USE_TIMER:
                    returnflag = 1
                    p2.x = p2.default_x
                    p2.y = p2.default_y
                    p2.speed = 0
                if item2_wait_time > ITEM_USE_TIMER:
                    returnflag = 1
                    p1.x = p1.default_x
                    p1.y = p1.default_y
                    p1.speed = 0
            elif p1.team == TEAM_2 and p2.team == TEAM_1:
                if item2_wait_time > ITEM_USE_TIMER:
                    returnflag = 1
                    p2.x = p2.default_x
                    p2.y = p2.default_y
                    p2.speed = 0
                if item1_wait_time > ITEM_USE_TIMER:
                    returnflag = 1
                    p1.x = p1.default_x
                    p1.y = p1.default_y
                    p1.speed = 0
            if returnflag:
                return
        angle = math.atan2(dy, dx) + 0.5 * math.pi
        total_mass = p1.mass + p2.mass
        (p1.angle, p1.speed) = addVectors((p1.angle, p1.speed*(p1.mass-p2.mass)/total_mass), (angle, 2*p2.speed*p2.mass/total_mass))
        #This necessitates that the board be put in only as p2... :/
        overlap = 0.5*(p1.size + p2.size - dist+1)
        p1.x += math.sin(angle)*overlap
        p1.y -= math.cos(angle)*overlap
        if not isinstance(p2, Board):
            (p2.angle, p2.speed) = addVectors((p2.angle, p2.speed*(p2.mass-p1.mass)/total_mass), (angle+math.pi, 2*p1.speed*p1.mass/total_mass))        
            p2.x -= math.sin(angle)*overlap
            p2.y += math.cos(angle)*overlap 



class Particle:
    """ A circular object with a velocity, size and mass """
    
    def __init__(self, (x, y), size, team, mass=1):
        self.x = x
        self.y = y
        self.default_x = x
        self.default_y = y
        self.size = size
        if (team == TEAM_1):
            self.colour = (0, 0 , 0)
        elif (team == TEAM_2):
            self.colour = (255, 255, 255)
        self.thickness = 0
        self.speed = 0
        self.angle = 0
        self.mass = mass
        self.team = team

    def move(self, fps):
        """ Update position based on speed, angle"""
        self.x += math.sin(self.angle) * self.speed * fps
        self.y -= math.cos(self.angle) * self.speed * fps

    def attract(self, particle, attract):
        """ Pulls particles towards each other """
        dx = self.x - particle.x
        dy = self.y - particle.y
        dist = math.hypot(dx, dy)
        theta = math.atan2(dy, dx)
        force = ATTRACT_FACTOR * self.mass * particle.mass
        if dist:
            force = force / dist**2
        if not attract:
            force = -force
        self.accelerate((theta - 0.5*math.pi, force/self.mass))
        particle.accelerate((theta + 0.5*math.pi, force/particle.mass))

    def accelerate(self, vector):
        """ Accelerate at a given angle and speed """
        (self.angle, self.speed) = addVectors((self.angle, self.speed), vector)

    def mouseMove(self, x, y):
        """ Change angle and speed to move towards a given point """

        dx = x - self.x
        dy = y - self.y
        self.angle = 0.5*math.pi + math.atan2(dy, dx)
        self.speed = math.hypot(dx, dy) * 0.1

class Board:
    """ A protective circle that stays in a fixed x-coordinate """

    def __init__(self, (x, y), size, team, boardnum):
        self.x = x
        #x start-point
        self.initx = x
        self.maxdist = 64
        self.y = y
        self.size = size
        self.team = team
        self.mass = 150
        self.speed = 8
        self.drift = 4
        self.boardnum = 0
        if (team == TEAM_1):
            self.colour = (0, 0 , 100)
        elif (team == TEAM_2):
            self.colour = (180, 180, 255)

    def move(self, (xdirection, ydirection), fps, height):
        """ Update position based on speed, angle"""
        if (not xdirection) and abs(self.initx - self.x) > 0.01:
            if (self.x > self.initx):
                self.x -= self.drift * fps
                if self.x < self.initx:
                    self.x = self.initx
            else:
                self.x += self.drift * fps
                if self.x > self.initx:
                    self.x = self.initx
        elif xdirection:
            if xdirection *(self.x - self.initx) < self.maxdist:
                self.x += xdirection * self.speed * fps
        self.y += ydirection * self.speed * fps
        if (self.y - self.size < 0) :
            self.y = self.size
        elif (self.y + self.size > height):
            self.y = height - self.size
        




class Environment:
    """ Defines the boundary of a simulation and its properties """
    
    def __init__(self, (width, height)):
        self.width = width
        self.height = height
        self.particles = []
        self.boards = []
        
        self.colour = (128,128,128)
        self.mass_of_air = 0
        self.acceleration = None
        self.score_1 = 0
        self.score_2 = 0
        self.goal_upper_limit = int(height / 5.0)
        self.goal_lower_limit = int(height * 4.0 / 5.0)
        self.curr_mass1 = INIT_MASS1
        self.curr_mass2 = INIT_MASS2
        self.item1_wait_count = item1_wait_time
        self.item2_wait_count = item2_wait_time
        
    def addParticles(self, n=1, **kargs):
        """ Add n particles with properties given by keyword arguments"""
        
        for i in range(n):
            mass = kargs.get('mass', 10)
            #size = (int) (mass/5)
            size = kargs.get('size', 35)
            x = kargs.get('x', random.uniform(size, self.width - size))
            y = kargs.get('y', random.uniform(size, self.height - size))
            team = kargs.get('team', 0)

            particle = Particle((x, y), size, team, mass)
            particle.speed = kargs.get('speed', 6)
            particle.angle = kargs.get('angle', random.uniform(0, math.pi*2))
            particle.colour = kargs.get('colour', (0, 0, 0))
            print "Added a particle"
            self.particles.append(particle)

    def addBoards(self, n=1, **kargs):
        """ Add n particles with properties given by keyword arguments"""
        for i in range(n):
            width = kargs.get('width', 10)
            height = kargs.get('height', 50)
            x = kargs.get('x', 10)
            y = kargs.get('y', 10)
            boardnum = kargs.get('boardnum', i)
            
            board = Board((x, y), width, height, boardnum)
            board.speed = kargs.get('speed', 8)

            self.boards.append(board)

    def addParticle(self, x, y, size=35, team=0, mass=100):
        particle = Particle((x, y), size, team, mass)
        self.particles.append(particle)
        self.curr_mass = mass

    def addBoard(self, x, y, size=50, team=0, mass=150):
        board = Board((x, y), size, team, mass)
        self.boards.append(board)

    def changeMass(self, mass1, mass2):
        if mass1:
            if self.curr_mass1 < 200 and mass1 == 1:
                self.curr_mass1 += 1
            elif self.curr_mass1 > 20 and mass1 == -1:
                self.curr_mass1 -= 1
            for i, particle in enumerate(self.particles):
                if particle.team == TEAM_1:
                    particle.mass = self.curr_mass1
        if mass2:
            if self.curr_mass2 < 200 and mass2 == 1:
                self.curr_mass2 += 1
            elif self.curr_mass2 > 20 and mass2 == -1:
                self.curr_mass2 -= 1
            for i, particle in enumerate(self.particles):
                if particle.team == TEAM_2:
                    particle.mass = self.curr_mass2

    def useItem(self, item1, item2):
        global item1_wait_time
        global item2_wait_time
        
        if item1:
            #If done wait time, and if not in use / use_time = 0
            if item1_wait_time <= 0:
                item1_wait_time = ITEM_WAIT_TIMER
        if item2:
            #If done wait time, and if not in use / use_time = 0
            if item2_wait_time <= 0:
                item2_wait_time = ITEM_WAIT_TIMER
            
    def update(self, fps, attract1, attract2, mass1, mass2, boardnum, item1, item2):
        """  Moves particles and tests for collisions with the walls and each other """
        global item1_wait_time
        global item2_wait_time
        
        #First update the masses
        self.changeMass(mass1, mass2)
        if item1_wait_time > 0:
            item1_wait_time -= fps
        else:
            item1_wait_time = 0
        if item2_wait_time > 0:
            item2_wait_time -= fps
        else:
            item2_wait_time = 0
        self.item1_wait_count = item1_wait_time
        self.item2_wait_count = item2_wait_time
        self.useItem(item1, item2)
        #If attract is false, then repulse
        for i, particle in enumerate(self.particles):
            particle.move(fps)
            self.bounce(particle)
            for j, board in enumerate(self.boards):
                collide(particle, board, fps)
            for particle2 in self.particles[i+1:]:
                collide(particle, particle2, fps)
                if (particle.team == particle2.team):
                    attract = attract1
                    if particle.team == TEAM_2:
                        attract = attract2
                    particle.attract(particle2, attract)
        for i, board in enumerate(self.boards):
            board.move((boardnum[2*i], boardnum[2*i+1]), fps, self.height)
            
    def bounce(self, particle):
        """ Tests whether a particle has hit the boundary of the environment """

        # Hit right side of screen
        if particle.x > self.width - particle.size:
            if particle.team == TEAM_1 and particle.y > self.goal_upper_limit and particle.y < self.goal_lower_limit :
                particle.x = particle.default_x
                particle.y = particle.default_y
                particle.speed = 0
                self.score_1 += 1
            else:
                particle.x = 2*(self.width - particle.size) - particle.x
                particle.angle = - particle.angle
        # Hit left side of screen
        elif particle.x < particle.size:
            if particle.team == TEAM_2 and particle.y > self.goal_upper_limit and particle.y < self.goal_lower_limit:
                particle.x = particle.default_x
                particle.y = particle.default_y
                particle.speed = 0
                self.score_2 += 1
            else:
                particle.x = 2*particle.size - particle.x
                particle.angle = - particle.angle

        if particle.y > self.height - particle.size:
            particle.y = 2*(self.height - particle.size) - particle.y
            particle.angle = math.pi - particle.angle

        elif particle.y < particle.size:
            particle.y = 2*particle.size - particle.y
            particle.angle = math.pi - particle.angle
        
    def findParticle(self, x, y):
        """ Returns any particle that occupies position x, y """
        
        for particle in self.particles:
            if math.hypot(particle.x - x, particle.y - y) <= particle.size:
                return particle
        return None
