#!/usr/bin/env python3
from evdev import InputDevice, list_devices, categorize, ecodes, ff
import rtmidi
import math
import numpy as np
import time

TARGET_NAME = "Generic X-Box pad"


CHORDS = {
    "BTN_A":    [],
    "BTN_NORTH":[],
    "BTN_WEST": [],
    "BTN_B":    [],
    "BTN_TR":   [],
    "BTN_TL":   [],
    "ABS_Z":    [],
}

ABS_TRIGGERS = {
    "ABS_Z": [70, 10, False],
    "ABS_RZ": [70, 100, False],
}

VELOCITY = 127
CHANNEL = 0  # MIDI channel 1
RECORDING_MODE = False # send note offs before note ons in strum mode?


# semitone patterns
MAJOR = [ 0, 2, 2, 1, 2, 2, 2, 1 ]
MINOR = [ 0, 2, 1, 2, 2, 1, 2, 2 ]
MAJOR_TALLY = []
MINOR_TALLY = []

MAIN_SCALE = "maj"
OFFSET = 0
CURRENT_CHORD = "main"
MAIN_CHORD = "main"
STRUM_MODE = False
STRUM_FOCUS: list[str] = ["", ""]

STRUM_CLOCK = 0
STRUM_POS = 0
CHORD_TO_STRUM = []
STRUM_WEIGHT = -0.25 # biases velocity towards notes at one end of the strum

CHORD_NAMES_CIRCLE = ["maj/min", "7", "maj/min7", "maj/min9", "sus4", "sus2", "dim", "aug"]
# clockwise from the top
# you can swap these out! (coming soon)
# default is ["maj/min", "7", "maj/min7", "maj/min9", "sus4", "sus2", "dim", "aug"]


JOYSTICK = [ 0, 0 ]


PRESSED_KEYS = set()

CURRENTLY_PRESSED = {}
TO_STOP = set()

CHANGES = { # [ octave shift, inversion ]
    "BTN_A":     [0,0],
    "BTN_NORTH": [0,0],
    "BTN_WEST":  [0,0],
    "BTN_B":     [0,0],
    "BTN_TR":    [0,0],
    "BTN_TL":    [0,0],
    "ABS_Z":     [0,0],
}



def tally() -> None:
    note_tally = 0
    global MAJOR_TALLY
    MAJOR_TALLY = []
    for note in MAJOR:
        MAJOR_TALLY.append(note + note_tally)
        note_tally += note
    note_tally = 0
    global MINOR_TALLY
    MINOR_TALLY = []
    for note in MINOR:
        MINOR_TALLY.append(note + note_tally)
        note_tally += note



def get_step(step: int=0, key: str="maj") -> int:
    if key == "maj":
        key_tally = MAJOR_TALLY
    elif key == "min":
        key_tally = MINOR_TALLY
    return ( step // 7 * 12 ) + key_tally[ step % 7 ]



def generate_scale(key: str = CURRENT_CHORD) -> None: # defines the chords played by each key

    if key == "main":
        key = MAIN_CHORD

    if key == "main":
        key = MAIN_SCALE

    if key == "maj" or key == "min" or key == "maj/min":
        if key == "maj/min":
            if MAIN_SCALE == "maj":
                key = "min"
            elif MAIN_SCALE == "min":
                key = "maj"
        for step, chord in enumerate(CHORDS):
            CHORDS[chord] = [
                60 + OFFSET + get_step(step  , key),
                60 + OFFSET + get_step(step+2, key),
                60 + OFFSET + get_step(step+4, key)
            ]
    elif key == "7":
        for step, chord in enumerate(CHORDS):
            CHORDS[chord] = [
                60 + OFFSET + get_step(step  , "maj"),
                60 + OFFSET + get_step(step+2, "maj"),
                60 + OFFSET + get_step(step+4, "maj"),
                60 + OFFSET + get_step(step+7, "min")
            ]
    elif key == "maj/min7":
        for step, chord in enumerate(CHORDS):
            CHORDS[chord] = [
                60 + OFFSET + get_step(step  , MAIN_SCALE),
                60 + OFFSET + get_step(step+2, MAIN_SCALE),
                60 + OFFSET + get_step(step+4, MAIN_SCALE),
                60 + OFFSET + get_step(step+7, MAIN_SCALE)
            ]
    elif key == "maj/min9":
        for step, chord in enumerate(CHORDS):
            CHORDS[chord] = [
                60 + OFFSET + get_step(step  , MAIN_SCALE),
                60 + OFFSET + get_step(step+2, MAIN_SCALE),
                60 + OFFSET + get_step(step+4, MAIN_SCALE),
                60 + OFFSET + 12 + get_step(step+2, MAIN_SCALE)
            ]
    elif key == "sus4":
        for step, chord in enumerate(CHORDS):
            CHORDS[chord] = [
                60 + OFFSET + get_step(step  , MAIN_SCALE),
                60 + OFFSET + get_step(step+3, MAIN_SCALE),
                60 + OFFSET + get_step(step+4, MAIN_SCALE),
            ]
    elif key == "sus2":
        for step, chord in enumerate(CHORDS):
            CHORDS[chord] = [
                60 + OFFSET + get_step(step  , MAIN_SCALE),
                60 + OFFSET + get_step(step+1, MAIN_SCALE),
                60 + OFFSET + get_step(step+4, MAIN_SCALE),
            ]
    elif key == "dim":
        for step, chord in enumerate(CHORDS):
            CHORDS[chord] = [
                60 + OFFSET + get_step(step  , MAIN_SCALE),
                60 + OFFSET + get_step(step  , MAIN_SCALE) + 3,
                60 + OFFSET + get_step(step  , MAIN_SCALE) + 6,
            ]
    elif key == "aug":
        for step, chord in enumerate(CHORDS):
            CHORDS[chord] = [
                60 + OFFSET + get_step(step  , MAIN_SCALE),
                60 + OFFSET + get_step(step  , MAIN_SCALE) + 4,
                60 + OFFSET + get_step(step  , MAIN_SCALE) + 8,
            ]
    elif key == "minimal9":
        for step, chord in enumerate(CHORDS):
            CHORDS[chord] = [
                60 + OFFSET + get_step(step  , MAIN_SCALE),
                60 + OFFSET + 12 + get_step(step+2, MAIN_SCALE)
            ]

    for key in CHORDS:
        # octave
        temp = []
        for note in CHORDS[key]:
            note += 12 * CHANGES[key][0]
            temp.append(note)
        CHORDS[key] = temp

        # inversions
        if CHANGES[key][1] >= 1:
            CHORDS[key][0] += 12
        if CHANGES[key][1] == 2:
            CHORDS[key][1] += 12

        CHORDS[key].sort()

        if len(CHORDS[key]) != len(set(CHORDS[key])):
            CHORDS[key][-1] += 12

        # # stacked octaves
        # temp = []
        # for note in CHORDS[key]:
        #     temp.append(note+12)
        # for note in temp:
        #     if not note in CHORDS[key]:
        #         CHORDS[key].append(note)
        # CHORDS[key].sort()


    change_on_the_fly()


def maj_min() -> str:
    if MAIN_SCALE == "maj":
        return "min"
    return "maj"



def change_on_the_fly() -> None: # change currently playing notes when joystick blah blah
    new_notes = set()
    to_register = []
    global CHORD_TO_STRUM
    for key in PRESSED_KEYS: # all currently pressed keys
        for note in CHORDS[key]:
            new_notes.add(note) # all notes that should be on now
            to_register.append( [note, key] )
    remove = []
    for note in CURRENTLY_PRESSED:
        if not note in new_notes:
            midi_out.send_message([0x80 | CHANNEL, note, 0]) # stop all notes that shouldn't be on
            remove.append(note)
    for note in remove:
        del CURRENTLY_PRESSED[note]
        while note in CHORD_TO_STRUM:
            CHORD_TO_STRUM.remove(note)
    for note in new_notes:
        if not STRUM_MODE:
            if not note in CURRENTLY_PRESSED:
                midi_out.send_message([0x90 | CHANNEL, note, VELOCITY]) # start all notes that now should be on
            else:
                if not note in CHORD_TO_STRUM:
                    CHORD_TO_STRUM.append(note)
                    CHORD_TO_STRUM.sort()
    CHORD_TO_STRUM = list(new_notes)
    CHORD_TO_STRUM.sort()
    for entry in to_register:
        register( entry[0],entry[1] )





def interpret_joystick() -> None:
    if math.sqrt(JOYSTICK[0]**2 + JOYSTICK[1]**2) < 0.5:
        chord = MAIN_CHORD
    else:
        ang = np.arctan2(JOYSTICK[0], JOYSTICK[1]) / math.pi * 4 + 0.875
        ang = int(ang//1)
        chord = CHORD_NAMES_CIRCLE[ang]
    global CURRENT_CHORD
    if CURRENT_CHORD != chord:
        CURRENT_CHORD = chord
        generate_scale(chord)




def register( note: int, source: str) -> None: # keep track of which notes are being played by which keys
    if not note in CURRENTLY_PRESSED:
        CURRENTLY_PRESSED[note] = [source]
    else:
        CURRENTLY_PRESSED[note].append(source)
    PRESSED_KEYS.add(source)



def try_release( note: int, source: str | None = None ) -> bool: # can we release this note or is something else also playing it?
    try:
        PRESSED_KEYS.remove(source)
    except:
        pass
    if note in CURRENTLY_PRESSED:
        while source in CURRENTLY_PRESSED[note]:
            CURRENTLY_PRESSED[note].remove(source)
        if CURRENTLY_PRESSED[note] == []:
            del CURRENTLY_PRESSED[note]
            return True
        else:
            return False
    else:
        return True
    # i also hate this logic.




def play_key( key: str ) -> None:
    global CHORD_TO_STRUM, STRUM_FOCUS
    # current problem releasing focused key doesnt stop it from playing
    chord = CHORDS[key]
    if not STRUM_MODE:
        for note in chord:
            register(note, key)
            midi_out.send_message([0x90 | CHANNEL, note, VELOCITY])
    else:
        # note off only when next chord is pressed (AND current note released?)
        # but this is next chord
        if key != STRUM_FOCUS[0]:
            pass
            # 0 is currently pressed 1 is previous
            # note off double prev chord (this doesn't work like this guaranteed)
            release_key(STRUM_FOCUS[1])
            # register new chord as current chord
            STRUM_FOCUS[1] = STRUM_FOCUS[0]
            STRUM_FOCUS[0] = key
            # and release prev chord if it's released
            if STRUM_FOCUS[1] not in PRESSED_KEYS:
                release_key(STRUM_FOCUS[1])
        for note in chord:
            register(note, key)
            if not note in CHORD_TO_STRUM:
                CHORD_TO_STRUM.append(note)
        CHORD_TO_STRUM.sort()

def release_key( key: str ) -> None:
    global CHORD_TO_STRUM, TO_STOP
    try:
        chord = CHORDS[key]
    except KeyError:
        return
    for note in chord:
        if try_release(note, key):
            l = []
            if note in CHORD_TO_STRUM:
                l.append(note)
            for note in l:
                CHORD_TO_STRUM.remove(note)
            if (key == STRUM_FOCUS[1] or not STRUM_MODE):
                midi_out.send_message([0x80 | CHANNEL, note, 0])


RUMBLE = 0

def try_strum( pressure: int, device: InputDevice ) -> None:
    global STRUM_POS, STRUM_CLOCK, RUMBLE
    sep = 1020 // (len(CHORD_TO_STRUM)+2) # make sure every note actually gets played
    positions = [10]
    for i, note in enumerate(CHORD_TO_STRUM):
        positions.append( sep*(1+i) )
    positions.append( sep*(1+len(CHORD_TO_STRUM)) )
    if STRUM_POS < pressure: # if trigger is pushing IN this frame:
        vel_modifier = 1+ STRUM_WEIGHT
    else:
        vel_modifier = 1- STRUM_WEIGHT

    # step /512 **(1+vel_modifier) * 127-> vel
    # strum clock and strum pos
    for i, step in enumerate(positions):
        if STRUM_POS <= step <= pressure or pressure <= step <= STRUM_POS: # if trigger just passed over a strummable note
            if i == 0 or i == len(positions)-1:
                STRUM_CLOCK = time.monotonic_ns()
            else:
                if RUMBLE != 0:
                    device.erase_effect(RUMBLE)
                step = step/1024 * 5
                elapsed = time.monotonic_ns() - STRUM_CLOCK
                elapsed *= len(CHORD_TO_STRUM)
                # increase divisor to bias louder
                vel = int(min( 127 / (elapsed / 30000000 ), 127)) # determine velocity by time between notes
                vel *= (1 / vel_modifier**(step)) # weigh the strum
                vel = int(min(vel, 127))
                if RECORDING_MODE:
                    midi_out.send_message([0x80 | CHANNEL, CHORD_TO_STRUM[i-1], 0])
                midi_out.send_message([0x90 | CHANNEL, CHORD_TO_STRUM[i-1], vel])
                RUMBLE = rumble(device, vel)
                STRUM_CLOCK = time.monotonic_ns()
    STRUM_POS = pressure


def rumble( device: InputDevice, strength: int ):
    rumble = ff.Rumble(strong_magnitude=0x0F00, weak_magnitude=(128+strength*384))
    effect_type = ff.EffectType(ff_rumble_effect=rumble)
    duration_ms = 100

    effect = ff.Effect(
        ecodes.FF_RUMBLE, -1, 0,
        ff.Trigger(0, 0),
        ff.Replay(duration_ms, 0),
        effect_type
    )
    repeat_count = 1
    effect_id = device.upload_effect(effect)
    device.write(ecodes.EV_FF, effect_id, repeat_count)
    return effect_id

def blame():
    pass # when notes are played, check the charts to see which keys played them

def save( slot: str ) -> None:
    slot += ".txt"
    with open(slot, "w") as file:
        file.write(MAIN_SCALE + "\n")
        file.write(str(OFFSET) + "\n")
        for key in CHANGES:
            file.write(str(CHANGES[key][0]) + " ")
            file.write(str(CHANGES[key][1]) + "\n")
        file.write("True" if STRUM_MODE else "False")
    print(f"saved to {slot}")

def load( slot: str ) -> None:
    global MAIN_SCALE, OFFSET, CHANGES, STRUM_MODE
    slot += ".txt"
    with open(slot) as file:
        MAIN_SCALE = file.readline().strip()
        OFFSET = int(file.readline().strip())
        for key in CHANGES:
            temp = file.readline().strip().split(" ")
            temp[0] = int(temp[0])
            temp[1] = int(temp[1])
            CHANGES[key] = temp
        strum = file.readline().strip()
        if strum == "True":
            STRUM_MODE = True
        elif strum == "False":
            STRUM_MODE = False
    print(f"loaded {slot}")
    generate_scale()




def main():

    # -------------------------------
    # 1. Find gamepad by name
    # -------------------------------
      # <-- change to your controller name

    device = None
    for path in list_devices():
        dev = InputDevice(path)
        if TARGET_NAME.lower() in dev.name.lower():
            device = dev
            break

    if not device:
        raise RuntimeError(f"Controller '{TARGET_NAME}' not found. Available devices:")
        for path in list_devices():
            print(InputDevice(path).name)
        exit(1)

    print(f"Using controller: {device.name} ({device.path})")

    global midi_out
    midi_out = rtmidi.MidiOut()
    midi_out.open_virtual_port("Gamepad Chords")


    tally()
    generate_scale()
    print("Listening for gamepad button presses...")

    global VELOCITY, OFFSET, MAIN_SCALE, CURRENT_CHORD, CHANGES, STRUM_MODE, ABS_TRIGGERS, CHORD_TO_STRUM, TO_STOP
    main_button_held = False
    save_button_held = False
    load_button_held = False
    # MAIN LOOP
    try:
        for event in device.read_loop():
            if event.type == ecodes.EV_KEY:
                key = categorize(event)
                button = key.keycode

                if button == "BTN_MODE":
                    if key.keystate == key.key_down:
                        main_button_held = True
                        if PRESSED_KEYS:
                            for key in PRESSED_KEYS:
                                CHANGES[key][1] = ( CHANGES[key][1] + 1 ) % 3
                            generate_scale()

                    elif key.keystate == key.key_up:
                        main_button_held = False

                if button == "BTN_SELECT":
                    if key.keystate == key.key_down:
                        save_button_held = True
                        if load_button_held:
                            load("default")
                    elif key.keystate == key.key_up:
                        save_button_held = False

                if button == "BTN_START":
                    if key.keystate == key.key_down:
                        load_button_held = True
                    elif key.keystate == key.key_up:
                        load_button_held = False

                if isinstance(button, list):
                    button = button[0]

                if button in CHORDS:
                    if load_button_held and key.keystate == key.key_down:
                        load(button)
                    elif save_button_held and key.keystate == key.key_down:
                        save(button)
                    else:
                        if key.keystate == key.key_down:
                            play_key(button)
                        elif key.keystate == key.key_up:
                            release_key(button)

            elif event.type == ecodes.EV_ABS:
                code = ecodes.ABS[event.code] if event.code in ecodes.ABS else None

                if code == "ABS_RZ": # velocity
                    note, threshold, active = ABS_TRIGGERS[code]
                    value = event.value
                    if main_button_held:
                        if not active and value > threshold:
                            STRUM_MODE = not STRUM_MODE
                            print("Strum mode is ON" if STRUM_MODE else "Strum mode is OFF")
                            ABS_TRIGGERS[code][2] = True
                            CHORD_TO_STRUM = []
                        elif active and value <= threshold:
                            ABS_TRIGGERS[code][2] = False
                    elif not STRUM_MODE:
                        VELOCITY = int( 127 - event.value/8 )
                    else:
                        try_strum(event.value, device)

                elif code in ABS_TRIGGERS: # the 7th scale degree is played by the left trigger
                    note, threshold, active = ABS_TRIGGERS[code]
                    value = event.value
                    if code in CHORDS:
                        if save_button_held:
                            save(code)
                        else:
                            if not active and value > threshold:
                                # Trigger note-on
                                play_key(code)
                                ABS_TRIGGERS[code][2] = True  # mark active
                            elif active and value <= threshold:
                                # Trigger note-off
                                release_key(code)
                                ABS_TRIGGERS[code][2] = False


                elif code == "ABS_X" or code == "ABS_Y": # process joystick values
                    if code == "ABS_X":
                        JOYSTICK[0] = event.value / 32768
                    elif code == "ABS_Y":
                        JOYSTICK[1] = 0 - (event.value / 32768)
                    interpret_joystick()

                elif code == "ABS_HAT0X": # change key
                    if main_button_held:
                        OFFSET = 0
                    else:
                        OFFSET += event.value
                    generate_scale()

                elif code == "ABS_HAT0Y":
                    if main_button_held and event.value != 0: # swap main scale
                        MAIN_SCALE = maj_min()
                        CURRENT_CHORD = "main"
                    elif PRESSED_KEYS and event.value != 0: # octave for selected chords
                        for key in PRESSED_KEYS:
                            CHANGES[key][0] -= event.value
                    else:
                        OFFSET -= 12* event.value # global octave
                    generate_scale()

                elif code == "ABS_RY":
                    for note in TO_STOP:
                        midi_out.send_message([0x80 | CHANNEL, note, 0])
                    TO_STOP.clear()


    except KeyboardInterrupt:
        pass

main()