# Integrating LLMs with SoftBank Pepper: a complete technical reference

**Pepper's Python 2.7 NAOqi framework can be bridged to modern LLM APIs using an HTTP/REST dual-process architecture — the dominant pattern across 15+ published research projects from 2023–2026.** This report covers the robot's full hardware stack, its NAOqi SDK and Choregraphe IDE, practical programming patterns for audio, tablet, and face detection, the Python 2↔3 bridge problem and its solutions, and a catalog of recent LLM integration projects with their architectures and lessons learned. The findings establish a clear technical roadmap for a master's thesis connecting ChatGPT, Claude, or other LLMs to Pepper.

---

## Pepper's hardware and software platform

Pepper is a **120 cm tall, 28 kg** semi-humanoid robot with **20 degrees of freedom** (2 head, 2×6 arm/hand, 2 hip, 1 knee, 3 omnidirectional base wheels). Its onboard computer runs an **Intel Atom E3845 quad-core CPU at 1.91 GHz** with **4 GB DDR3 RAM** and **8 GB flash storage** plus a micro-SD slot. The operating system is **NAOqi OS**, a modified **Gentoo Linux** distribution, running **Python 2.7** natively.

The sensor suite includes **two 5 MP RGB cameras** (forehead and chin, OV5640), an **ASUS Xtion 3D depth sensor** (320×240, 0.4–8 m range) behind the eyes, **4 directional microphones** on the head for sound localization, **2 speakers** in the ears, **2 sonar sensors**, **6 laser line generators**, **2 infrared sensors**, **3 bumper contact sensors**, **3 head capacitive touch sensors**, **2 hand touch sensors**, and gyroscope/accelerometer IMUs in both torso and base.

The chest-mounted **10.1-inch IPS capacitive touchscreen** runs at **1280×800 resolution** with 5-point multitouch, powered by a separate 1.3 GHz quad-core ARM Cortex-A7 with 1 GB RAM and 32 GB storage. The tablet communicates with the robot's head computer over an internal network at IP **198.18.0.1**. Battery capacity is **30 Ah / 795 Wh lithium-ion**, providing roughly 8–10 hours of active use.

Two OS variants exist: **NAOqi 2.5** (Python/C++ SDK, Choregraphe-compatible, ~1,000+ APIs) and **NAOqi 2.9** (Android-based, QiSDK for Java/Kotlin, ~20 high-level APIs, no Choregraphe). For LLM integration work using Python, NAOqi 2.5 is the standard choice. Aldebaran filed for bankruptcy in February 2025; its IP was acquired by Maxvision Technology Corp. (Shenzhen) in July 2025, and no new units are being manufactured.

---

## NAOqi framework, PyNAOqi, and programmatic connection

NAOqi is the **middleware broker** running on port **9559** that loads modules at startup and provides lookup services for method discovery. Every module — ALTextToSpeech, ALMotion, ALMemory, and dozens more — registers its methods with the broker, enabling both **local procedure calls** (in-process, zero-copy) and **remote procedure calls** (over TCP, serialized). PyNAOqi is the Python 2.7 binding that exposes this entire API.

PyNAOqi is **not pip-installable**. It must be downloaded manually from the SoftBank Robotics developer portal as a platform-specific archive (e.g., `pynaoqi-python2.7-2.5.5.5-linux64.tar.gz`). Installation requires extracting the archive and setting `PYTHONPATH` to include the SDK's `lib/python2.7/site-packages` directory. On Windows, **32-bit Python 2.7** is required to match the 32-bit native bindings, plus the MSVC++ 2010 x86 redistributable.

Two connection paradigms exist. The **legacy ALProxy** approach creates direct proxies:

```python
from naoqi import ALProxy
tts = ALProxy("ALTextToSpeech", "192.168.1.100", 9559)
tts.say("Hello from ALProxy!")
```

The **modern qi.Session** approach uses a shared session object:

```python
import qi
session = qi.Session()
session.connect("tcp://192.168.1.100:9559")
tts = session.service("ALTextToSpeech")
tts.say("Hello from qi.Session!")
```

The eleven most important NAOqi modules for LLM integration work are:

- **ALTextToSpeech** — converts text to speech on the robot's speakers; supports speed/pitch parameters and RSPD/VCT tags
- **ALAnimatedSpeech** — speech synchronized with gestures; annotation tags like `^start(animations/Stand/Gestures/Hey_1)` trigger concurrent animations, with body language modes `contextual`, `random`, or `disabled`
- **ALMotion** — joint-level motor control; `wakeUp()`/`rest()` toggle stiffness, `setAngles()` for non-blocking moves, `angleInterpolation()` for timed trajectories
- **ALAudioRecorder** — records microphone audio to WAV/OGG files on the robot filesystem
- **ALAudioDevice** — real-time audio streaming via `processRemote` callback; supports 16 kHz or 48 kHz, 1 or 4 channels
- **ALSpeechRecognition** — on-board keyword recognition with a predefined vocabulary; results stored in ALMemory under `"WordRecognized"`; universally considered inadequate for open-domain speech
- **ALMemory** — the central key-value store and event bus; `subscriber("EventName").signal.connect(callback)` enables reactive programming
- **ALFaceDetection** — OMRON-based face detection; publishes to `"FaceDetected"` event with face position, size, and optional recognition data
- **ALLeds** — RGB control of eye, ear, chest, and foot LEDs via `fadeRGB("FaceLeds", 0xFF0000, 0.5)`
- **ALTabletService** — controls the chest tablet display (Pepper only)
- **ALBehaviorManager** — lists, runs, and stops Choregraphe behaviors installed on the robot

---

## Choregraphe as a visual programming IDE

Choregraphe is a **desktop visual programming environment** (Windows, macOS, Linux) that uses a box-and-wire flow diagram paradigm. It works **only with NAOqi 2.5** — version 2.5.5.5 or 2.5.10/11 for Pepper. Installation requires downloading from the developer portal and entering a license key. The suite bundles a **virtual robot simulator** (naoqi-bin) and **200+ pre-built animation boxes**.

To connect to a physical Pepper, the robot and computer must be on the same WiFi network. Press Pepper's chest button to hear its IP address, then enter this IP in Choregraphe's Connection Panel (port 9559). Every Choregraphe box contains an editable **Python 2.7 script** with lifecycle methods: `onLoad()`, `onUnload()`, `onInput_onStart()`, and `onInput_onStop()`. Boxes communicate through typed input/output signals (Bang, Number, String, Dynamic).

Key features include the **Timeline Editor** for keyframe animation, the **Dialog Editor** using QiChat syntax, and the **Robot View** for real-time pose monitoring. Behaviors deploy as `.pkg` packages via `File > Build Application Package` or through `ALBehaviorManager` programmatically.

**For a thesis integrating LLMs, standalone Python scripts are strongly preferred over Choregraphe.** Choregraphe excels at animation prototyping and simple demos, but its box paradigm becomes cumbersome for complex logic, external API calls, and version control. Standalone scripts offer full Python flexibility, standard Git workflows, and natural integration with bridge servers. The recommended workflow is: use Choregraphe to design and test animations, then export them as behaviors and trigger them programmatically from standalone scripts.

---

## Audio capture for speech recognition

Two approaches exist for capturing audio from Pepper's four microphones, both critical for feeding speech to cloud STT engines like Whisper.

**ALAudioRecorder** is the simpler file-based approach. It records directly to the robot's filesystem:

```python
recorder = session.service("ALAudioRecorder")
recorder.startMicrophonesRecording(
    "/home/nao/speech.wav", "wav", 16000, [0, 0, 1, 0]  # front mic only
)
time.sleep(5)
recorder.stopMicrophonesRecording()
```

The channel selection array `[Left, Right, Front, Rear]` uses 0/1 flags. Supported combinations are: **4 channels at 48 kHz** or **1 channel at 16 kHz**, in WAV or OGG format. All audio is **16-bit signed PCM**. Files are retrieved from the robot via SCP/Paramiko (`ssh nao@<IP>`, default password `nao`).

**ALAudioDevice with processRemote** provides real-time streaming. You create a module that inherits from ALModule and implements a `processRemote(nbChannels, nbSamples, timeStamp, buffer)` callback. This requires setting up an ALBroker on the client side:

```python
class SoundReceiverModule(ALModule):
    def __init__(self, name):
        ALModule.__init__(self, name)
        self.audio = ALProxy("ALAudioDevice")
        self.audio.setClientPreferences(self.getName(), 16000, 3, 0)  # front channel
        self.audio.subscribe(self.getName())

    def processRemote(self, nbChannels, nbSamples, timeStamp, inputBuffer):
        sound_data = np.frombuffer(inputBuffer, dtype=np.int16)
        # Process or accumulate audio data
```

**For LLM integration, the recommended approach** is ALAudioRecorder at **16 kHz, single channel (front mic), WAV format** — this matches the input requirements of Whisper and most cloud STT APIs. Record on the robot, transfer via Paramiko, transcribe on the bridge server. Key pitfalls: ALSpeechRecognition and ALAudioRecorder **cannot run simultaneously** (both compete for microphone access), and you must call `stopMicrophonesRecording()` before attempting to read the file.

---

## Tablet display and custom HTML interfaces

ALTabletService controls the 1280×800 chest tablet via the internal network. The tablet runs a built-in browser that loads content from the robot's web server at `http://198.18.0.1/apps/`. Core methods:

```python
tablet = session.service("ALTabletService")
tablet.loadUrl("https://example.com")    # load external URL
tablet.showWebview()                      # display the webview
tablet.showImage("http://198.18.0.1/apps/my-app/photo.jpg")
tablet.executeJS("document.title")        # run JavaScript in the page
tablet.hideWebview()                      # return to idle screen
```

**Local HTML files** are placed in an app's `html/` directory and served at `http://198.18.0.1/apps/APP_ID/index.html`. The `loadApplication("app-name")` method automatically loads the app's `index.html`. Custom HTML pages should include the viewport meta tag `<meta name="viewport" content="width=1280, user-scalable=no" />` and can import the NAOqi JavaScript SDK at `/libs/qimessaging/2/qimessaging.js` to create bidirectional communication — the HTML page can call `ALMemory.raiseEvent()` to send data back to Python, or use `ALTabletBinding.raiseEvent()` to trigger the `onJSEvent` signal.

For an LLM integration thesis, the tablet is ideal for displaying conversation transcripts, showing visual context (images from the camera), or presenting interactive UI elements. Touch events are accessible via `onTouchDown(x, y)` signals.

---

## Face detection to trigger interactions

ALFaceDetection uses OMRON technology to detect faces via the top camera. Subscribe to the `"FaceDetected"` event in ALMemory to react when someone approaches:

```python
face_det = session.service("ALFaceDetection")
memory = session.service("ALMemory")
face_det.subscribe("MyApp")
subscriber = memory.subscriber("FaceDetected")
subscriber.signal.connect(on_face_detected)
```

The `FaceDetected` event returns a nested structure: `[TimeStamp, [FaceInfo1, FaceInfo2, ..., FilteredRecoInfo], CameraPose, CameraId]`. Each `FaceInfo` contains `ShapeInfo` (alpha/beta angular position, face width/height) and `ExtraInfo` (face ID, recognition score, learned name, eye/nose/mouth coordinates). Detection works at face widths as small as **20 pixels** (~2 m in QVGA, ~4 m in VGA). Face learning via `learnFace("PersonName")` enables recognition across sessions, though it is less robust than detection for varied angles. Tracking can be enabled with `face_det.enableTracking(True)` for persistent face following.

---

## The Python 2.7 to 3.x bridge problem and its solutions

The fundamental challenge is that **NAOqi/PyNAOqi requires Python 2.7**, while OpenAI, Anthropic, Whisper, LangChain, and essentially all modern AI libraries require **Python 3.8+**. Five architectural patterns address this.

**Pattern 1: HTTP/REST bridge (dominant approach).** A Flask or FastAPI server runs Python 3.x on a laptop/server, exposing endpoints like `/chat` and `/transcribe`. Pepper's Python 2.7 code uses `urllib2` to send JSON requests. This is used by ilabsweden/pepperchat, the Frontiers ASD therapy paper, and at least six other published projects. A minimal bridge server:

```python
# Python 3.x bridge server
from flask import Flask, request, jsonify
import openai
app = Flask(__name__)
client = openai.OpenAI(api_key="sk-...")

@app.route('/chat', methods=['POST'])
def chat():
    msg = request.json['message']
    response = client.chat.completions.create(
        model="gpt-4", messages=[{"role":"user","content":msg}])
    return jsonify({'response': response.choices[0].message.content})

app.run(host='0.0.0.0', port=5000)
```

**Pattern 2: Socket-based communication.** Lower latency (~10–50 ms vs 50–200 ms for HTTP). Used by Pepper-GPT (University of Auckland) and the Ghent University elder care project. Better for audio streaming scenarios.

**Pattern 3: ROS2 bridge.** The `naoqi_driver2` package publishes NAOqi sensor data, audio, and camera frames as ROS2 topics, enabling integration with any Python 3 ROS2 node. Higher setup complexity but powerful for multi-robot or complex perception pipelines.

**Pattern 4: MQTT broker.** Used by LAIR-GPT (Università Politecnica delle Marche). Components publish/subscribe to MQTT topics over local WiFi, decoupling Pepper control from LLM processing.

**Pattern 5: Python 3 qi library (qi 3.1.5).** Aldebaran released a Python 3-compatible qi package (installable via `pip install qi==3.1.5`, Linux x86_64 only). It supports remote connections to NAOqi on Pepper, but **some functionality is broken** — touch detection, certain event callbacks, and some audio APIs do not work. This is suitable for simple prototyping but not production.

The HTTP/REST bridge is recommended for a thesis project: it is the most battle-tested pattern, straightforward to debug, and cleanly separates concerns. Typical end-to-end latency (speech → STT → LLM → TTS → speech) is **2–5 seconds**, dominated by cloud API round-trips.

---

## Catalog of LLM + Pepper projects (2023–2026)

At least **15 GitHub repositories** and **17 academic papers** document LLM integration with Pepper. The following table summarizes the most significant:

| Project | Institution | LLM | STT | Bridge | Year |
|---|---|---|---|---|---|
| **ilabsweden/pepperchat** | U. Skövde, Sweden | GPT-3/4 | Google Cloud Speech | Dual-process (Py2+Py3) | 2023 |
| **UoA-CARES/Pepper-GPT** | U. Auckland | GPT-3.5-turbo | Whisper Small | Socket over VPN | 2023 |
| **studerus/pepper-android-realtime-chat** | Independent | GPT-4o Realtime / Gemini Live | End-to-end speech-to-speech | QiSDK (Android native) | 2026 |
| **LAIRLabUnivpm/LAIR-GPT** | U. Politecnica delle Marche | GPT-3.5-turbo | Whisper | MQTT | 2024 |
| **rosielab/Pepper-GPT** | ROSIE Lab | Mistral (local/Ollama) | Text input only | ROS + Docker | 2024 |
| **hsaine/PepperChat** | Various | GPT-3 | IBM Watson | Direct NAOqi | 2023 |

Three patterns dominate across projects. **OpenAI Whisper** is the most popular STT choice, typically the `base` or `small` model run on a GPU-equipped companion PC. **Pepper's built-in ALTextToSpeech** is nearly universally used for TTS — only the Ghent University project substituted ElevenLabs neural TTS for more natural prosody. **GPT-3.5-turbo** was the most commonly deployed LLM through 2024, with GPT-4o and Gemini emerging in 2025–2026 projects.

The most architecturally advanced project is **studerus/pepper-android-realtime-chat** (HRI '26), which uses **QiSDK on NAOqi 2.9** to bypass the Python 2.7 problem entirely. It implements end-to-end speech-to-speech via OpenAI's Realtime API and Google Gemini Live API, with **function calling for agentic robot control** — the LLM can invoke navigation, gaze positioning, LED changes, and camera vision as tool calls. It also streams video at 1 FPS to Gemini for real-time visual context. This represents the current state of the art.

Key academic findings include: the HU Utrecht study (ACM ICSEB 2024) found **cloud-based LLMs substantially outperformed local models** (Ollama/TinyLlama) in interaction quality and user satisfaction; the Nature Scientific Reports study (2025) deployed Pepper+ChatGPT "in the wild" at an Australian festival (n=88) and found mixed emotional resonance with concerns about diversity/inclusion; and the Frontiers ASD therapy paper (2023) demonstrated using facial emotion recognition to feed emotional context to ChatGPT for personalized therapeutic interactions.

---

## Conclusion

The technical foundation for connecting LLMs to Pepper is well-established. **The HTTP/REST bridge pattern with a Flask/FastAPI server is the recommended starting architecture** — it cleanly separates Pepper's Python 2.7 NAOqi layer from the Python 3.x AI stack, is used by the majority of published projects, and requires no specialized infrastructure. For audio, record with ALAudioRecorder at 16 kHz on the front microphone, transfer via Paramiko, and transcribe with Whisper. Use ALAnimatedSpeech (not plain ALTextToSpeech) for output to leverage Pepper's gesture system. Display conversation context on the tablet via custom HTML loaded through ALTabletService.

Three emerging trends merit attention for a thesis started in 2026. First, **QiSDK on NAOqi 2.9** eliminates the Python 2.7 constraint entirely but requires Android/Kotlin development and sacrifices Choregraphe compatibility. Second, **speech-to-speech models** (OpenAI Realtime API, Gemini Live) bypass the STT→LLM→TTS pipeline for dramatically lower latency. Third, **function calling / tool use** enables LLMs to control the robot agentically — selecting gestures, navigating, and using sensors based on conversational context rather than hard-coded logic. The studerus/pepper-android-realtime-chat framework (HRI '26) demonstrates all three and is the strongest reference implementation for new work.