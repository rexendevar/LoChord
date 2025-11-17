#!/usr/bin/env python3
from evdev import InputDevice, list_devices, categorize, ecodes, ff
import rtmidi
import math
import numpy as np
import time

TARGET_NAME = "Generic X-Box pad"
CHANNEL = 0  # MIDI channel 1
RECORDING_MODE = False # send note offs before note ons in strum mode?
CHORD_NAMES_CIRCLE = ["maj/min", "7", "maj/min7", "maj/min9", "sus4", "sus2", "dim", "aug"]
# clockwise from the top
# you can swap these out! (coming soon)
# default is ["maj/min", "7", "maj/min7", "maj/min9", "sus4", "sus2", "dim", "aug"]

STRUM_WEIGHT = -0.25 # biases velocity towards notes at one end of the strum
DEADZONE = 0.5 # how far from center does the stick have to move to change chords

DO_RUMBLE = True
GUITAR_MODE = True # stacks more notes for each chord. very nice



class LoChord:
    def __init__(self) -> None:
        # you can change things in this section if they don't work right, but you shouldn't have to.
        self.chords: dict[ str, list[int] ] = {
            "BTN_A":    [], # A
            "BTN_NORTH":[], # X
            "BTN_WEST": [], # Y
            "BTN_B":    [], # B
            "BTN_TR":   [], # right bumper
            "BTN_TL":   [], # left bumper
            "ABS_Z":    [], # left trigger
        }
        self.abs_triggers = {
            "ABS_Z": [70, 10, False], # left trigger
            "ABS_RZ": [70, 100, False], # right trigger
        }


        # this section is for variables that change dynamically
        # fucking with scales & chords
        self.main_scale: str = "maj"
        self.main_chord: str = "main" # coming sometime: configuring default chords & such
        self.offset: int = 0
        self.changes: dict[ str, list[int] ] = { # [ octave shift, inversion ]
            "BTN_A":     [0,0],
            "BTN_NORTH": [0,0],
            "BTN_WEST":  [0,0],
            "BTN_B":     [0,0],
            "BTN_TR":    [0,0],
            "BTN_TL":    [0,0],
            "ABS_Z":     [0,0],
        }
        # joystick
        self.current_chord: str = "main"
        self.joystick: list[float] = [ 0.0, 0.0 ]
        # strum mode
        self.strum_mode: bool = False
        self.chord_to_strum: list[int] = []
        self.strum_clock: int = 0 # in nanoseconds
        self.strum_pos: int = 0 # trigger depth out of 1023
        self.strum_focus: list[str] = ["", ""]
        self.velocity: int = 127
        self.rumble = 0 # evdev effect id but idk what data type it is
        self.unstopped: set[int] = set()
        self.stop_state: int = -1 # for tracking manual note-offs
        # general note/button tracking
        self.pressed_keys: set = set()
        self.currently_pressed: dict[ int, list[str] ] = {}
        self.to_stop: set = set()
        self.main_held: bool = False
        self.save_held: bool = False
        self.load_held: bool = False

        # this section is constants.
        self.major = [ 0, 2, 2, 1, 2, 2, 2, 1 ]
        self.minor = [ 0, 2, 1, 2, 2, 1, 2, 2 ]
        self.major_tally = []
        self.minor_tally = []
        self.tally()
        self.generate_scale()


    def tally(self) -> None:
        note_tally = 0
        self.major_tally = []
        for note in self.major:
            self.major_tally.append(note + note_tally)
            note_tally += note
        note_tally = 0
        self.minor_tally = []
        for note in self.minor:
            self.minor_tally.append(note + note_tally)
            note_tally += note



    def get_step(self, step: int=0, key: str="maj") -> int:
        if key == "maj":
            key_tally = self.major_tally
        elif key == "min":
            key_tally = self.minor_tally
        return ( step // 7 * 12 ) + key_tally[ step % 7 ]


    def maj_min(self) -> str:
        if self.main_scale == "maj":
            return "min"
        return "maj"


    def generate_scale(self, key: str = "") -> None:
        '''define all chords'''
        if not key:
            key = self.current_chord
        if key == "main":
            key = self.main_chord
        if key == "main":
            key = self.main_scale

        if key == "maj" or key == "min" or key == "maj/min":
            if key == "maj/min":
                if self.main_scale == "maj":
                    key = "min"
                elif self.main_scale == "min":
                    key = "maj"
            for step, chord in enumerate(self.chords):
                self.chords[chord] = [
                    60 + self.offset + self.get_step(step  , key),
                    60 + self.offset + self.get_step(step+2, key),
                    60 + self.offset + self.get_step(step+4, key),
                ]
                if GUITAR_MODE:
                    self.chords[chord].append(60 + self.offset + self.get_step(step  , key) + 12)
                    self.chords[chord].append(60 + self.offset + self.get_step(step+2, key) + 12)
        elif key == "7": # check this
            for step, chord in enumerate(self.chords):
                start = self.get_step(step, self.main_scale)
                self.chords[chord] = [
                    60 + self.offset + start,
                    60 + self.offset + start + 4,
                    60 + self.offset + start + 7,
                    60 + self.offset + start + 10,
                ]
                if GUITAR_MODE:
                    self.chords[chord].append(60 + self.offset + start + 12)
                    #self.chords[chord].append(60 + self.offset + self.get_step(step+2, key) + 12)

        elif key == "maj/min7": # this probably works for all except dim
            for step, chord in enumerate(self.chords):
                self.chords[chord] = [
                    60 + self.offset + self.get_step(step  , self.main_scale),
                    60 + self.offset + self.get_step(step+2, self.main_scale),
                    60 + self.offset + self.get_step(step+4, self.main_scale),
                    60 + self.offset + self.get_step(step+7, self.main_scale)
                ]
                if GUITAR_MODE:
                    self.chords[chord].append( 60 + self.offset + self.get_step(step, self.main_scale) + 12 )
        elif key == "maj/min9": # probably all except diminished
            for step, chord in enumerate(self.chords):
                self.chords[chord] = [
                    60 + self.offset + self.get_step(step  , self.main_scale),
                    60 + self.offset + self.get_step(step+2, self.main_scale),
                    60 + self.offset + self.get_step(step+4, self.main_scale),
                    60 + self.offset + 12 + self.get_step(step+2, self.main_scale)
                ]
                if GUITAR_MODE:
                    self.chords[chord].append( 60 + self.offset + 12 + self.get_step(step+4, self.main_scale) )
        elif key == "sus4": # almost certainly wrong
            for step, chord in enumerate(self.chords):
                start = self.get_step(step, self.main_scale)
                self.chords[chord] = [
                    60 + self.offset + start,
                    60 + self.offset + start + 5,
                    60 + self.offset + start + 7,
                ]
                if GUITAR_MODE:
                    self.chords[chord].append(60 + self.offset + start + 12)
                    self.chords[chord].append(60 + self.offset + start + 17)
        elif key == "sus2":
            for step, chord in enumerate(self.chords):
                start = self.get_step(step, self.main_scale)
                self.chords[chord] = [
                    60 + self.offset + start,
                    60 + self.offset + start + 2,
                    60 + self.offset + start + 7,
                ]
                if GUITAR_MODE:
                    self.chords[chord].append(60 + self.offset + start + 12)
                    self.chords[chord].append(60 + self.offset + start + 14)
        elif key == "dim": # im not sure i know what these two are.
            for step, chord in enumerate(self.chords):
                start = self.get_step(step, self.main_scale)
                self.chords[chord] = [
                    60 + self.offset + start,
                    60 + self.offset + start + 3,
                    60 + self.offset + start + 6,
                ]
                if GUITAR_MODE:
                    self.chords[chord].append(60 + self.offset + start + 12)
                    self.chords[chord].append(60 + self.offset + start + 15)
        elif key == "aug":
            for step, chord in enumerate(self.chords):
                start = self.get_step(step, self.main_scale)
                self.chords[chord] = [
                    60 + self.offset + start,
                    60 + self.offset + start + 4,
                    60 + self.offset + start + 8,
                ]
                if GUITAR_MODE:
                    self.chords[chord].append(60 + self.offset + start + 12)
                    self.chords[chord].append(60 + self.offset + start + 16)
        elif key == "minimal9": # tonic and 9th nothing else
            for step, chord in enumerate(self.chords):
                self.chords[chord] = [
                    60 + self.offset + self.get_step(step  , self.main_scale),
                    60 + self.offset + 12 + self.get_step(step+2, self.main_scale)
                ]

        for key in self.chords: # apply octave/inversion
            # octave
            temp = []
            for note in self.chords[key]:
                note += 12 * self.changes[key][0]
                temp.append(note)
            self.chords[key] = temp

            # inversions
            if self.changes[key][1] >= 1:
                self.chords[key][0] += 12
            if self.changes[key][1] == 2:
                self.chords[key][1] += 12
            self.chords[key].sort()
            # inversion: if newly pitched up note overlaps 7th or 9th, pitch up the 7th or 9th also
            # REVISIT THIS cause it's BROKEN
            if len(self.chords[key]) != len(set(self.chords[key])):
                self.chords[key][-1] += 12

        self.change_on_the_fly()



    def change_on_the_fly(self) -> None:
        '''change out actively playing chord by doing note-ons/note-offs. TODO: figure out strum integration'''
        new_notes = set()
        to_register = []
        for key in self.pressed_keys: # all currently pressed keys
            for note in self.chords[key]:
                new_notes.add(note) # all notes that should be on now
                to_register.append( [note, key] )
        remove = []
        for note in self.currently_pressed:
            if not note in new_notes:
                midi_out.send_message([0x80 | CHANNEL, note, 0]) # stop all notes that shouldn't be on
                remove.append(note)
        for note in remove:
            del self.currently_pressed[note]
            while note in self.chord_to_strum:
                self.chord_to_strum.remove(note)
        for note in new_notes:
            if not self.strum_mode:
                if not note in self.currently_pressed:
                    midi_out.send_message([0x90 | CHANNEL, note, self.velocity]) # start all notes that now should be on
                else:
                    if not note in self.chord_to_strum:
                        self.chord_to_strum.append(note)
                        self.chord_to_strum.sort()
        self.chord_to_strum = list(new_notes)
        self.chord_to_strum.sort()
        for entry in to_register:
            self.register( entry[0],entry[1] )


    def interpret_joystick(self) -> None:
        '''do trigonometry to change to the right chord'''
        if math.sqrt(self.joystick[0]**2 + self.joystick[1]**2) < DEADZONE:
            chord = self.main_chord
        else:
            ang = np.arctan2(self.joystick[0], self.joystick[1]) / math.pi * 4 + 0.875
            ang = int(ang//1)
            chord = CHORD_NAMES_CIRCLE[ang]
        if self.current_chord != chord:
            self.current_chord = chord
            self.generate_scale(chord)



    def play_key( self, key: str ) -> None:
        '''key is pressed, do logic to see what happens'''
        chord = self.chords[key]
        if not self.strum_mode:
            for note in chord:
                self.register(note, key)
                midi_out.send_message([0x90 | CHANNEL, note, self.velocity])
        else:
            if key != self.strum_focus[0]:
                # note-off double prev chord (this MIGHT not work?)
                self.release_key(self.strum_focus[1])
                # register new chord as current chord
                self.strum_focus[1] = self.strum_focus[0]
                self.strum_focus[0] = key
                # and release prev chord if it's released
                self.release_key(self.strum_focus[1], self.strum_focus[1] not in self.pressed_keys)
            for note in chord:
                self.unstopped.add(note)
                self.register(note, key)
                if not note in self.chord_to_strum:
                    self.chord_to_strum.append(note)
            self.chord_to_strum.sort()


    def register( self, note: int, source: str) -> None:
        '''we keep track of which notes are being played by which keys'''
        if not note in self.currently_pressed:
            self.currently_pressed[note] = [source]
        else:
            self.currently_pressed[note].append(source)
        self.pressed_keys.add(source)



    def release_key( self, key: str, full: bool = True ) -> None:
        '''key is released, do logic to see what happens'''
        try:
            chord = self.chords[key]
        except KeyError:
            return
        for note in chord:
            if self.try_release(note, key):
                l = []
                if note in self.chord_to_strum:
                    l.append(note)
                for note in l:
                    self.chord_to_strum.remove(note)
                if (key == self.strum_focus[1] or not self.strum_mode) and full:
                    midi_out.send_message([0x80 | CHANNEL, note, 0])


    def try_release( self, note: int, source: str | None = None ) -> bool:
        '''can we release this note or is something else playing it too?'''
        try:
            self.pressed_keys.remove(source)
        except:
            pass
        if note in self.currently_pressed:
            while source in self.currently_pressed[note]:
                self.currently_pressed[note].remove(source)
            if self.currently_pressed[note] == []:
                del self.currently_pressed[note]
                return True
            else:
                return False
        else:
            return True
        # i also hate this logic.



    def all_notes_off(self) -> None:
        '''stop all currently playing notes'''
        # yes i know i could send an all notes off message but there are caveats
        self.chord_to_strum = []
        self.pressed_keys = set()
        self.strum_focus = ["", ""]
        for note in self.unstopped:
            midi_out.send_message([0x80 | CHANNEL, note, 0])
        self.unstopped = set()


    def try_strum( self, pressure: int, device: InputDevice ) -> None:
        '''process right trigger to strum and rumble the controller'''
        sep = 1020 // (len(self.chord_to_strum)+2) # make sure every note actually gets played
        positions = [10]
        for i, note in enumerate(self.chord_to_strum):
            positions.append( sep*(1+i) )
        positions.append( sep*(1+len(self.chord_to_strum)) )
        if self.strum_pos < pressure: # if trigger is pushing IN this frame:
            vel_modifier = 1+ STRUM_WEIGHT
        else:
            vel_modifier = 1- STRUM_WEIGHT

        # fully press and release trigger with nothing sleected to stop all notes
        if self.pressed_keys: # disqualify
            self.stop_state = -1
        elif pressure == 0 and self.stop_state == 2: # stop all notes
            self.all_notes_off()
            self.stop_state = 0
        elif pressure == 0 or self.strum_pos == 0:
            self.stop_state = 1
        elif pressure == 1023 and self.stop_state == 1:
            self.stop_state = 2

        for i, step in enumerate(positions):
            if self.strum_pos <= step <= pressure or pressure <= step <= self.strum_pos: # if trigger just passed over a strummable note
                if i == 0 or i == len(positions)-1:
                    self.strum_clock = time.monotonic_ns()
                else:
                    if self.rumble != 0:
                        device.erase_effect(self.rumble)
                    step = step/1024 * 5
                    elapsed = time.monotonic_ns() - self.strum_clock
                    elapsed *= len(self.chord_to_strum)
                    # increase divisor to bias louder VVV
                    vel = int(min( 127 / (elapsed / 30000000 ), 127)) # determine velocity by time between notes
                    vel *= (1 / vel_modifier**(step)) # weigh the strum
                    vel = int(min(vel, 127))
                    if RECORDING_MODE:
                        midi_out.send_message([0x80 | CHANNEL, self.chord_to_strum[i-1], 0])
                    midi_out.send_message([0x90 | CHANNEL, self.chord_to_strum[i-1], vel])
                    self.rumble = self.do_rumble(device, vel)
                    self.strum_clock = time.monotonic_ns()
        self.strum_pos = pressure


    def do_rumble( self, device: InputDevice, strength: int ):
        '''rumble the controller. returns an effect_id which is a data type i don't know.'''
        if not DO_RUMBLE:
            return 0
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



    def save( self, slot: str ) -> None:
        '''save current configuration to a text file'''
        slot += ".txt"
        with open(slot, "w") as file:
            file.write(self.main_scale + "\n")
            file.write(str(self.offset) + "\n")
            for key in self.changes:
                file.write(str(self.changes[key][0]) + " ")
                file.write(str(self.changes[key][1]) + "\n")
            file.write("True" if self.strum_mode else "False")
        print(f"saved to {slot}")


    def load( self, slot: str ) -> None:
        '''load configuration from text file. NOT RESILIENT!!!!!!!!!!!!!!! NO error handling yet'''
        slot += ".txt"
        with open(slot) as file:
            self.main_scale = file.readline().strip()
            self.offset = int(file.readline().strip())
            for key in self.changes:
                temp = file.readline().strip().split(" ")
                temp[0] = int(temp[0])
                temp[1] = int(temp[1])
                self.changes[key] = temp
            strum = file.readline().strip()
            if strum == "True":
                self.strum_mode = True
            elif strum == "False":
                self.strum_mode = False
        print(f"loaded {slot}")
        self.generate_scale()




    def process_frame(self, event) -> None:
        '''does all the heavy lifting'''
        if event.type == ecodes.EV_KEY:
            key = categorize(event)
            button = key.keycode

            if button == "BTN_MODE":
                if key.keystate == key.key_down:
                    self.main_held = True
                    if self.pressed_keys:
                        for key in self.pressed_keys:
                            self.changes[key][1] = ( self.changes[key][1] + 1 ) % 3
                        self.generate_scale()

                elif key.keystate == key.key_up:
                    self.main_held = False

            if button == "BTN_SELECT":
                if key.keystate == key.key_down:
                    self.save_held = True
                    if self.load_held:
                        self.load("default")
                elif key.keystate == key.key_up:
                    self.save_held = False

            if button == "BTN_START":
                if key.keystate == key.key_down:
                    self.load_held = True
                elif key.keystate == key.key_up:
                    self.load_held = False

            if isinstance(button, list):
                button = button[0]

            if button in self.chords:
                if self.load_held and key.keystate == key.key_down:
                    self.load(button)
                elif self.save_held and key.keystate == key.key_down:
                    self.save(button)
                else:
                    if key.keystate == key.key_down:
                        self.play_key(button)
                    elif key.keystate == key.key_up:
                        self.release_key(button)

        elif event.type == ecodes.EV_ABS:
            code = ecodes.ABS[event.code] if event.code in ecodes.ABS else None

            if code == "ABS_RZ": # velocity
                note, threshold, active = self.abs_triggers[code]
                value = event.value
                if self.main_held:
                    if not active and value > threshold:
                        self.strum_mode = not self.strum_mode
                        print("Strum mode is ON" if self.strum_mode else "Strum mode is OFF")
                        self.abs_triggers[code][2] = True
                        self.chord_to_strum = []
                    elif active and value <= threshold:
                        self.abs_triggers[code][2] = False
                elif not self.strum_mode:
                    self.velocity = int( 127 - event.value/8 )
                else:
                    self.try_strum(event.value, device)

            elif code in self.abs_triggers: # the 7th scale degree is played by the left trigger
                note, threshold, active = self.abs_triggers[code]
                value = event.value
                if code in self.chords:
                    if not active and value > threshold:
                        # Trigger note-on
                        if self.save_held:
                            self.save(code)
                        else:
                            self.play_key(code)
                        self.abs_triggers[code][2] = True  # mark active
                    elif active and value <= threshold:
                        # Trigger note-off
                        self.release_key(code)
                        self.abs_triggers[code][2] = False


            elif code == "ABS_X" or code == "ABS_Y": # process joystick values
                if code == "ABS_X":
                    self.joystick[0] = event.value / 32768
                elif code == "ABS_Y":
                    self.joystick[1] = 0 - (event.value / 32768)
                self.interpret_joystick()

            elif code == "ABS_HAT0X": # change key
                if self.main_held:
                    self.offset = 0
                else:
                    self.offset += event.value
                self.generate_scale()

            elif code == "ABS_HAT0Y":
                if self.main_held and event.value != 0: # swap main scale
                    self.main_scale = self.maj_min()
                    self.current_chord = "main"
                elif self.pressed_keys and event.value != 0: # octave for selected chords
                    for key in self.pressed_keys:
                        self.changes[key][0] -= event.value
                else:
                    self.offset -= 12* event.value # global octave
                self.generate_scale()

            # elif code == "ABS_RY":
            #     for note in TO_STOP:
            #         midi_out.send_message([0x80 | CHANNEL, note, 0])
            #     TO_STOP.clear()



def main():
    global device
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
    midi_out.open_virtual_port("LoChord")

    lc = LoChord()
    print("Listening for gamepad button presses...")

    try:
        for event in device.read_loop():
            lc.process_frame(event)
    except KeyboardInterrupt:
        pass



main()