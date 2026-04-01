"""OmniLLM AI Server package.

Contains the Flask HTTP bridge server and the NAOqi Python 2.7 client
for the Pepper robot integration.

Modules
-------
:mod:`omnillm.server.app`
    Flask AI server — receives audio/text from Pepper, runs the LangGraph
    pipeline, returns RobotAction JSON.

:mod:`omnillm.server.naoqi_client`
    Python 2.7 NAOqi client — runs on/near the Pepper robot, captures audio,
    calls the AI server, and executes responses on the robot hardware.
"""
