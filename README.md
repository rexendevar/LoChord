# Intro
This is a VERY EARLY WORK IN PROGRESS tool for transforming controller inputs into MIDI chords on Linux, very similar to the functionality of the HiChord. The basic controls are:

- A X Y B Rb Lb Lt - scale degrees (in order)
- Left stick - modify chord (the diagram is the same as on the HiChord)
- Right trigger - velocity control and strum
- Select, start - save, load
- D-pad - octave and key control
- Central button - wildcard

Each scale degree button will play its respective scale degree. LoChord starts in C Major by default.

# Setup (Linux)
Currently this is only built for Linux. I think you need kernel module `uinput` plus you need your user to be in the input group which requires sudo. After that, run `evtest` and check your controller's output to see what your buttons are called, because you'll probably have to rename all of them in the CHORDS section of the script. Also make sure the controller name is right.

Make sure u have Python modules `evdev` and `python-rtmidi`. The rest should already be installed if u have Python.

Once it's configured, running the script will create a MIDI node in your audio system, which you'll likely need to manually connect to your DAW using a patchbay program such as Helvum. After that it's connected and should work.

# Setup (Windows)
- use loopMIDI to make a midi port called LoChord
- use AntiMicroX and bind the guide button to F13 (no there is NOT an easier way)

install python modules `ctypes` `threading` `python-rtmidi` `numpy` and `atexit`. then run the script. you're gonna have to stop it and edit it. then run it again. then connect the midi device to your daw (slightly better setup process coming soon)

# Setup (MacOS)
Doesn't exist. Feel free to contribute!

## Joystick
The joystick is set up exactly like on the HiChord. Go look at a photo to see the arrangement.

## Saving and loading
LoChord has seven save slots corresponding to the seven scale degrees. To save to a slot, hold down Select and press the slot's respective scale degree. To load from a slot, hold Start and press the scale degree you want to load. (Which scale degree you use has no effect on the save itself - they're just slots.)

LoChord's save slots store:
- primary key (major or minor)
- master offset (semitones from middle C)
- octave and inversion for each chord separately
- whether or not you are in Strum Mode

You can load the default state (middle C major) by holding Start and pressing Select.

## Strum Mode
LoChord's strum mode lays out each note of the current chord along the travel of the right trigger. This allows you to strum the notes in a more natural and human way. Only works with analog triggers.

Readme is a work in progress. Use the main button + right trigger to toggle strum mode, then hold down a chord button and press right trigger in and out to strum. Fully press and release the trigger (with no chord button pressed) to manually stop all notes. 

Switching chords can take a little practice!
- To STOP the current chord before the next one, press the next chord's button and THEN release the current chord button.
- To CONTINUE the current chord legato-style, release the current chord's button and then press the next chord's button. The current chord will stop when the next strum begins.

Strum mode is subject to:
- STRUM_WEIGHT - Makes notes louder at one end of the strum. By default notes at the end will be slightly louder, which is kind of guitar-like I think.
- VELOCITY_SENSITIVITY - It's nonlinear.
- Note-safe mode - On by default, toggled with `load` + right trigger. Sends note-offs before note-ons instead of letting note-ons possibly pile up. Certain samplers (Ample Sound mainly) sound better if you disable this but BEWARE!

## Lead mode
Lead mode turns a chord into only one note. Useful for bass - might be useful for soloing if you can figure out the technique? Toggle it with `save` + right trigger. Compatible with strum mode but NOT compatible with bass or guitar mode.

The joystick becomes octave and pitch bend.

## Bass and guitar mode
Bass mode adds an extra note below the fundamental. Guitar mode adds notes to each chord so there's 5 per chord (plus bass if it's on). Toggle these with `main` + dpad left and right respectively.

## Transposing and inverting
D-pad up and down changes the octave, either of the whole scale or of whichever chords are actively held down. D-pad up/down + main button switches the primary scale between major & minor.

D-pad left & right changes the key a semitone at a time. D-pad l/r + main button resets to middle C.

Any chord button + main button cycles between inversions.

# To do
VERY VERY early version here. Still want to do
- more versatile strum mode so u can do ska & other better music DONE
- strum weighting where low strings play louder on upstroke or something DONE
- refine the joystick cause some of the chords are wrong for sure DONE
- lead mode
- configurable larger chords e.g. 2 octaves of a triad stacked, bass note etc
- rewrite it all with a class so i'm not misusing global vars so badly DONE
- windows version DONE but it sucks a bit
- put it in a ras pi for my dawless setup
- integrate my new evil features better
- ill think of more

# demo
https://youtu.be/D8k8uARDoKQ
