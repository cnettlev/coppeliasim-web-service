from flask import Blueprint, request, Response
import portpicker
import sim
from time import sleep

from PIL import Image
import io
import numpy as np
from random import shuffle

simulator = Blueprint('simulator', __name__, template_folder='templates')

cameras = []
cview = 0
client = None
playing = False
loading = [Image.open("static/loading_0.jpg"),Image.open("static/loading_1.jpg"),Image.open("static/loading_2.jpg"),Image.open("static/loading_3.jpg")]
shuffle(loading)
cLoading = 0
againIn = 0.1

def verboseResp(resp,func):
    print("Client: ",client," - Port",PORT," - Function:", func," - ", resp)

def reset():
    global cview, cameras, client, playing
    cameras = []
    cview = 0
    client = None
    playing = False

@simulator.route("/shuffleLoading")
def shuffleLoading():
    global loading
    shuffle(loading)
    return "0"

@simulator.route("/startStopSim")
def startStopSim():
    global  PORT, client, cameras

    if client is None:
        # No client, then Start

        PORT = int(request.args.get('port'))

        print("waiting")
        while portpicker.is_port_free(PORT):
            sleep(5*againIn)
            print(".")

        client=sim.simxStart('127.0.0.1',PORT,True,True,5000,5)
        verboseResp(client,"simxStart")

        return str(client)
    else:
        # There is a client, then Stop
        stop()
        sleep(.5)
        response = sim.simxSetIntegerSignal(client,'doClose',1,sim.simx_opmode_oneshot_wait)
        verboseResp(response,"simxSetIntegerSignal doClose")
        try:
            finish()
        except:
            verboseResp("already finished?","finish")
        reset()
        if response == -1:
            return "-1"
        else:
            return "0"


@simulator.route("/setCameraBuffer")
def setCameraBuffer():
    global cameras, client
    v = 0
    cameras = []
    while True:
        [response,view] = sim.simxGetObjectHandle(client,"view_"+str(v),sim.simx_opmode_blocking)
        verboseResp(response,"simxGetObjectHandle view"+str(v))
        if response > 0:
            break
        cameras.append(view)
        v += 1
        sleep(0.3)

    for view in cameras:
        [resp2,res,img] = sim.simxGetVisionSensorImage(client,view,0,sim.simx_opmode_streaming)
        verboseResp(resp2,"simxGetVisionSensorImage view"+str(view))
    return str(-1*(response==1))

def getFrame():
    global client, cLoading, loading, cameras, cview

    if len(cameras)>0 and cview < len(cameras) and client is not None:
        verboseResp(len(cameras),cview)
        response,resolution,image=sim.simxGetVisionSensorImage(client,cameras[cview],0,sim.simx_opmode_buffer)
        verboseResp(response,"simxGetVisionSensorImage")
        if len(resolution)==0:
            im = loading[cLoading]
        else:
            im = Image.frombuffer("RGB", (resolution[0],resolution[1]), np.array(image,dtype=np.uint8), "raw", "RGB", 0, 1)
    else:
        im = loading[cLoading]
    imgByteArr = io.BytesIO()
    im.save(imgByteArr, format="jpeg")

    return imgByteArr.getvalue()

def generateVideoStream():
    while True:
        sleep(0.01)

        frame = getFrame()

        if frame == None :
            continue

        yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + 
            bytearray(frame) + b'\r\n')

@simulator.route("/changeView")
def changeView():
    global cameras, cview, cLoading, client

    if client == None:
        cLoading = (cLoading+1)%len(loading)
    else:
        cview = (cview+1)%len(cameras)

    return "0"

@simulator.route("/videoStream")
def videoStream():
    # return the response generated along with the specific media
    # type (mime type)
    return Response(generateVideoStream(),
        mimetype = "multipart/x-mixed-replace; boundary=frame")

@simulator.route("/findAPort")
def findAPort():
    global PORT
    PORT = portpicker.pick_unused_port()
    return str(PORT)

@simulator.route("/playPause")
def playPause():
    global client, playing
    if client == None:
        return "0"
    if playing:
        return pause()
    else:
        return play()

@simulator.route("/restart")
def restart():
    ans = 0 + (stop() == "0")
    sleep(1)
    ans += (play() == "0")
    return str(ans)

@simulator.route("/play")
def play():
    global client, playing
    if client == None:
        return "-1"
    response = sim.simxStartSimulation(client,sim.simx_opmode_blocking)
    while response == 1:
        verboseResp(response,"simxStartSimulation")
        response = sim.simxStartSimulation(client,sim.simx_opmode_blocking)
        sleep(againIn)
    verboseResp(response,"simxStartSimulation")
    playing = (response == 0)
    return str(response)

@simulator.route("/pause")
def pause():
    global client, playing
    if client == None:
        return "-1"
    response = sim.simxPauseSimulation(client,sim.simx_opmode_blocking)
    while response == 1:
        verboseResp(response,"simxPauseSimulation")
        response = sim.simxPauseSimulation(client,sim.simx_opmode_blocking)
        sleep(againIn)
    if response == 0:
        playing = False
    verboseResp(response,"simxPauseSimulation")
    return str(response)

@simulator.route("/stop")
def stop():
    global client, playing
    if client == None:
        return "-1"
    response = sim.simxStopSimulation(client,sim.simx_opmode_blocking)
    while response == 1:
        verboseResp(response,"simxStopSimulation")
        response = sim.simxStopSimulation(client,sim.simx_opmode_blocking)
        sleep(againIn)
    if response == 0:
        playing = False
    verboseResp(response,"simxStopSimulation")
    return str(response)

@simulator.route("/finish")
def finish():
    global client
    if client == None:
        return "-1"
    response = sim.simxFinish(client)
    verboseResp(response,"simxFinish")
    return str(response)

@simulator.route("/loadScene")
def loadScene():
    global client

    if client is None:
        return "-1"

    scene = request.args.get('scene')

    stop()
    response=sim.simxLoadScene(client,scene,0xFF,sim.simx_opmode_blocking)
    while response == 1:
        verboseResp(response,"simxLoadScene "+scene)
        response = sim.simxLoadScene(client,scene,0xFF,sim.simx_opmode_blocking)
        sleep(againIn)
    verboseResp(response,"simxLoadScene "+scene)
    if not response:
        while setCameraBuffer()=="-1":
            sleep(againIn)
        return play()

    return str(response)
