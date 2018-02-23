# Pendulum Bot by Danny Walker, 2018
# http://danny.makesthings.work || https://walkerdanny.github.io
# CC BY-NC-SA 4.0
# Soon to be a major motion picture
# See https://github.com/walkerdanny/Pendulum_Bowl for the non-bot code and explanation

# Runs once a day, eventually as a cron job but at the moment it's manual.

# Import that good good
import numpy as np
import datetime
import subprocess
import random
import tweepy
import config

def velMag(theta_v_input, phi_v_input): # Function to calculate the magnitude of the angular velocities. Kina obvious.
    mag = np.sqrt(theta_v_input*theta_v_input + phi_v_input*phi_v_input)
    return mag

def dist2Bottom (x_in, y_in, z_in): # Calculates the distance between a point and the bottom of the "bowl"
    global L
    dist = np.sqrt(x_in**2 + y_in**2 + (z_in+L)**2)
    return dist

def linear_scale(variable, minIn, maxIn, minOut, maxOut): # Surely I don't need to implement this myself? Can't numpy already do this?
    # It's only y = mx + c scaling!
    m = (maxOut-minOut)/(maxIn-minIn)
    c = minOut - m * minIn
    return m*variable + c

def update_bob(): # Iteration function to update the data array for each timestep
    # A bob is the thing on the end of a pendulum, I didn't call my data array Bob or anything.
    global data
    global friction

    theta = data[0]
    theta_v = data[1]
    theta_a = data[2]

    phi = data[3]
    phi_v = data[4]
    phi_a = data[5]

    # Equations of motion of the system:
    theta_a = (np.sin(np.radians(theta))*np.cos(np.radians(theta))*phi_v*phi_v) - ((g/L)*np.sin(np.radians(theta)))

    # This line is commented out because of... reasons.
    #phi_a = -2*phi_v*theta_v*(np.cos(np.radians(theta))/np.sin(np.radians(theta)))
    # If you actually implement the acceleration in phi, bear in mind it tends to infinity as theta approaches zero, and you should deal with this.
    # My solution is to ignore it and pretend phi_v is constant

    # This is a really basic physics engine
    phi_a = phi_a_in
    theta_v += theta_a
    phi_v += phi_a

    # Simulate some viscous friction!
    theta_v *= friction
    phi_v *= friction

    theta += theta_v
    phi += phi_v

    # Calculate the Cartesian coordinates again
    xPos = L*np.sin(np.radians(theta))*np.cos(np.radians(phi))
    yPos = L*np.sin(np.radians(theta))*np.sin(np.radians(phi))
    zPos = -L*np.cos(np.radians(theta))

    # ...and fill up the data array again before returning it
    data = [theta, theta_v, theta_a, phi, phi_v, phi_a, xPos, yPos, zPos]

    return data

def frange(start, stop, step): # Range of floats, which apparently I do have to do myself?!
    arr = []
    i = start
    while i < stop:
        arr.append(i)
        i += step
    return arr


num_points = 1000 # Number of timesteps to simulate
fn = 20 # The "fineness" of the curved shapes in OpenSCAD. Higher is better, but greatly increases render time. 20 is good for me.

# Minimum and maximum radii of the spheres which draw the path. Tweak these to whatever your printer can comfortably handle and what looks good

minRad = random.choice(frange(0.5,1,0.1))
maxRad = random.choice(frange(1.2,3,0.1))

L = random.randrange(50,90,1) # Length of the pendulum
g = -random.randrange(20,60,1) # Gravity. I know, I'm sorry.
friction = random.choice(frange(0.998,1,0.0001)) # Viscous friction. Velocities multiply by this each timestep. Set to 1 for frictionless.

theta_in = random.randrange(60,120,1)  # Initial starting angle. Theta is the angle that traces "up and down the walls of the bowl" or whatever
theta_v_in = 0 # Initial starting angular velocity in theta. Zero is equivalent to dropping it, anything else and you're giving it a shove
theta_a_in = 0 # Initial acceleration, not much point in using it as it'll be overwritten on the first timestep

phi_in = 0 # Initial angle "around the edge of the bowl". Kind of pointless to set it as you'll be getting a 3D model, but whatever
phi_v_in = random.choice(frange(0.3,2,0.1)) # Speed at which the pendulum moves around the edge of the bowl. Warning: if you set this too large you end up with a ring shape!
phi_a_in = 0 # Again, kind of useless since phi_a is fixed at zero

# Calcualate the Cartesian coordinates of the initial conditions
xPos_in = L*np.sin(np.radians(theta_in))*np.cos(np.radians(phi_in))
yPos_in = L*np.sin(np.radians(theta_in))*np.sin(np.radians(phi_in))
zPos_in = -L*np.cos(np.radians(theta_in))

# Fill up the data array for the inial conditions. This then gets iterated at each timestep.
data = [theta_in, theta_v_in, theta_a_in, phi_in, phi_v_in, phi_a_in, xPos_in, yPos_in, zPos_in]

initialConditionsString = "Minimum Radius: " + str(minRad) + "\nMaximum Radius: " + str(maxRad) + "\nLength: " + str(L) + "\nGravity: " + str(g) + "\nFriction: " + str(friction) + "\nPhi Velocity: " + str(phi_v_in) + "\n"
print initialConditionsString

# Set up a new array to store the traced points (with an extra column for velocity)
thePointz = np.zeros((num_points,4))

# Do the iteration for the amount of timesteps and fill the array up!
for i in xrange(num_points):
    data = update_bob()
    thePointz[i] = [data[6], data[7], -data[8], velMag(data[1], data[4])]

maxVel = np.amax(thePointz[:,3])
minVel = np.amin(thePointz[:,3])

drawBase = False;
openscad_string = '/*\n' + initialConditionsString + '*/\n'

for i in xrange(num_points-1):
    thisPoint = thePointz[i]
    nextPoint = thePointz[i+1]

    if dist2Bottom(nextPoint[0],nextPoint[1],nextPoint[2]) < 5:
        drawBase = True

    # Linear interpolation to calculate the radii as a function of the velocity
    r1 = linear_scale(thisPoint[3], minVel, maxVel, minRad, maxRad)
    r2 = linear_scale(nextPoint[3], minVel, maxVel, minRad, maxRad)

    # Eugh...
    # TO DO: This, but better.
    openscad_string += 'hull($fn=%(fn)f){\n' % {'fn':fn}
    openscad_string += '\ttranslate([%(xZero)f, %(yZero)f, %(zZero)f]){\n' % {"xZero":thisPoint[0], "yZero": thisPoint[1], "zZero": thisPoint[2]}
    openscad_string += '\t\tsphere(%(rad)f, $fn=%(fn)f);\n' % {'rad':r1, 'fn':fn}
    openscad_string += '\t}\n'
    openscad_string += '\ttranslate([%(xZero)f, %(yZero)f, %(zZero)f]){}\n' % {"xZero":-thisPoint[0], "yZero": -thisPoint[1], "zZero": -thisPoint[2]}
    openscad_string += '\ttranslate([%(xOne)f, %(yOne)f, %(zOne)f]){\n' % {"xOne":nextPoint[0], "yOne": nextPoint[1], "zOne": nextPoint[2]}
    openscad_string += '\t\tsphere(%(rad)f, $fn=%(fn)f);\n' % {'rad':r2, 'fn':fn}
    openscad_string += '\t}\n'
    openscad_string += '\ttranslate([%(xOne)f, %(yOne)f, %(zOne)f]){}\n' % {"xOne":-nextPoint[0], "yOne": -nextPoint[1], "zOne": -nextPoint[2]}
    openscad_string += '};\n'


# This line adds on a circular "base" to the bottom of the "bowl". You might not want this, but it helps it print and stand up and stuff.
if drawBase:
    openscad_string += 'translate([%(xThree)f, %(yThree)f, %(zThree)f]){\n\tcylinder(h=5, r1 = %(r)f, r2 = %(r)f, center=true, $fn=%(fn)f);\n};' % {'xThree': 0, 'yThree': 0,'zThree':-L, 'r': L/3,'fn': 100}

fileName = str(datetime.datetime.now().strftime("%Y-%m-%d"))
print fileName

cadFileName = fileName + ".scad"
cadFile = open(cadFileName,'w')
cadFile.write(openscad_string)
cadFile.close()

# conditionsName = fileName + ".txt"
# conditions = open(fileName, 'w')
# conditions.write(initialConditionsString)
# conditions.close()

# All this shit needs porting to Unix

cameraArg = "--camera=0,0,%(transZ)f,55,0,25,%(zoomOut)f" % {"transZ":-L/2,"zoomOut": L*5} # argument for rendering an image
lastArg = "-o" + fileName + ".png"

# Pick a random colour scheme for some variety
colorschemes = ["Cornfield","Sunset","Metallic","Starnight","BeforeDawn","Nature","DeepOcean"]
colorschemeArg = "--colorscheme=" + random.choice(colorschemes)

# Generate an image from the "thrown-together" preview in OpenSCAD
print "Generating image..."
picName = fileName + '.png'
subprocess.check_output(["C:\Program Files\OpenSCAD\openscad.com", cadFileName, "--imgsize=1024,512", "--autocenter",colorschemeArg,"--projection=p", cameraArg, lastArg], shell=True)
print "Generated image: " + picName

# Generate the STL, takes AAAAAGGGEEEEESSSS
print "Generating STL..."
lastArg = "-o" + fileName + ".stl"
subprocess.check_output(["C:\Program Files\OpenSCAD\openscad.com", cadFileName, lastArg], shell=True) # Get the STL in about an hours time..
print "STL generated: " + fileName + ".stl"

# Git it good
subprocess.check_output(['git', 'add', '-A'], shell=True)
subprocess.check_output(['git', 'commit', '-m \"Added ' + fileName + '.stl and .scad\"' ], shell=True)
subprocess.check_output(['git', 'push'], shell=True)

# Do a tweet
auth = tweepy.OAuthHandler(config.api_key, config.api_secret)
auth.set_access_token(config.access_token, config.access_token_secret)
twitter = tweepy.API(auth)

STLURL = "https://github.com/walkerdanny/PendulumBot/blob/master/" + fileName + ".stl"

twitter.update_with_media(picName, initialConditionsString + STLURL)

# Could that be it?!?
