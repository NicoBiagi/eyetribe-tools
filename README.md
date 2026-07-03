\# eyetribe-tools



Python tools for using the Eye Tribe eye tracker without the EyeTribe UI.



Features:



\- start EyeTribe server at 60 Hz

\- select monitor and setup distances

\- check whether eyes are detected

\- calibrate and validate

\- save validation quality

\- run transparent gaze overlay/logger



\## Requirements



\- Windows

\- Eye Tribe server installed at:

&#x20; `C:\\Program Files (x86)\\EyeTribe\\Server\\EyeTribe.exe`

\- Python 3.10+



\## Usage



```python

from eyetribe\_tools import run\_eyetribe\_session\_gui



run\_eyetribe\_session\_gui()

