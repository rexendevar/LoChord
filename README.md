# Intro
This is a VERY EARLY WORK IN PROGRESS tool for transforming controller inputs into MIDI chords on Linux, very similar to the functionality of the HiChord. The basic controls are: 

- A X Y B Rb Lb Lt - scale degrees (in order)
- Left stick - modify chord (the diagram is the same as on the HiChord)
- Right trigger - velocity control and strum
- Select, start - save, load
- D-pad - octave and key control
- Central button - wildcard

Each scale degree button will play its respective chord, from I to vii in the Nashville numbering system. LoChord starts in C Major by default.

# Setup
Currently this is only built for Linux. I think you need kernel module `uinput` plus you need your user to be in the input group which requires sudo. After that, run `evtest` and check your controller's output to see what your buttons are called, because you'll probably have to rename all of them in the CHORDS section of the script. Also make sure the controller name is right.

Make sure u have Python modules `evdev` and `rtmidi` and make sure it's the RIGHT rtmidi because apparently there's more than one. The rest should already be installed if u have Python.

Once it's configured, running the script will create a MIDI node in your audio system, which you'll likely need to manually connect to your DAW using a patchbay program such as Helvum. After that it's connected and should work.

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
LoChord's strum mode lays out each note of the current chord along the travel of the right trigger. This allows you to strum the notes in a more natural and human way. 

Readme is a work in progress. Use the main button + right trigger to toggle strum mode, then hold down a chord button and press right trigger in and out to strum. Only works with analog triggers.

## other stuff

D-pad up and down changes the octave, either of the whole scale or of whichever chords are actively held down. D-pad up/down + main button switches the primary scale between major & minor.

D-pad left & right changes the key a semitone at a time. D-pad l/r + main button resets to middle C.

Any chord button + main button cycles between inversions.

# To do
VERY VERY early version here. Still want to do
- more versatile strum mode so u can do ska & other better music
- strum weighting where low strings play louder on upstroke or something
- refine the joystick cause some of the chords are wrong for sure
- lead mode
- configurable larger chords e.g. 2 octaves of a triad stacked, bass note etc
- rewrite it all with a class so i'm not misusing global vars so badly
- ill think of more

# demo
https://youtu.be/D8k8uARDoKQ
