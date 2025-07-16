import math
import hashlib
import itertools
import struct
import os
import bsdiff4
import pkgutil
import unicodedata

from typing import TYPE_CHECKING
import settings
import Utils
from worlds.Files import APDeltaPatch

from . import Items
from .Locations import ID_BASE
from .Options import CourseOrder, ShuffleDriftAbilities, ConsistentItemBoxes

if TYPE_CHECKING:
    from . import MK64World


# ROM ADDRESSES
class Addr:
    # *** ROM ADDRESSES ***
    # ** Native **
    COURSE_IDS = 0xF37B4
    COURSE_NAMEPLATES = 0x12F772
    RESULTS_MUSIC_REPETITIONS = 0xBDA883
    # ** Basepatch **
    SAVE = 0xC00000
    SAVE_SIZE = 0x200
    SAVE_LOCKED_ITEM_CLUSTERS = SAVE + 0x1B
    SAVE_LOCKED_ITEM_CLUSTERS_SIZE = 9
    SAVE_UNCHECKED_LOCATIONS = SAVE_LOCKED_ITEM_CLUSTERS + SAVE_LOCKED_ITEM_CLUSTERS_SIZE
    SAVE_UNCHECKED_LOCATIONS_SIZE = 56
    SAVE_IDENTIFIED_ITEM_BOXES = SAVE_UNCHECKED_LOCATIONS + SAVE_UNCHECKED_LOCATIONS_SIZE
    SAVE_IDENTIFIED_ITEM_BOXES_SIZE = 43
    PLAYER_NAME = SAVE + SAVE_SIZE
    PLAYER_NAME_SIZE = 64
    SEED_NAME = PLAYER_NAME + PLAYER_NAME_SIZE
    SEED_NAME_SIZE = 20
    GENERATION_DONE = SEED_NAME + SEED_NAME_SIZE
    GENERATION_LOCKED = GENERATION_DONE + 1
    # Game Settings
    TWO_PLAYER_POWERS = GENERATION_LOCKED + 1
    GAME_MODE = TWO_PLAYER_POWERS + 1
    MIRROR_COURSES = GAME_MODE + 1
    TWO_LAP_COURSES = MIRROR_COURSES + 2
    FREE_MINI_TURBO = TWO_LAP_COURSES + 2
    SHUFFLE_RAILINGS = FREE_MINI_TURBO + 1
    FEATHER_AVAILABLE = SHUFFLE_RAILINGS + 1
    CONSISTENT_ITEM_BOXES = FEATHER_AVAILABLE + 1
    ENGINE_CLASSES = CONSISTENT_ITEM_BOXES + 1
    # Generation Flags
    # AP Items and pickup strings
    ITEMS = 0xC002C8  # APItem[583] at 3 bytes each
    ITEM_SIZE = 3
    PICKUP_PLAYER_NAMES = 0xC009A0  # char[220][16]
    ASCII_PLAYER_NAME_SIZE = 16
    PICKUP_ITEM_NAMES = 0xC01760  # char[220][40]
    ITEM_NAME_SIZE = 40

    # *** RAM ADDRESSES ***
    GAME_STATUS_BYTE = 0x400019
    NUM_ITEMS_RECEIVED = 0x40001A
    LOCATIONS_UNCHECKED = 0x400024
    ENGINE_CLASSES_RAM = 0x400260
    RECEIVE_ITEM_ID = 0x40028E
    RECEIVE_CLASSIFICATION = RECEIVE_ITEM_ID + 1
    RECEIVE_PLAYER_NAME = RECEIVE_CLASSIFICATION + 1
    RECEIVE_ITEM_NAME = RECEIVE_PLAYER_NAME + ASCII_PLAYER_NAME_SIZE


def generate_rom_patch(world: "MK64World", output_directory: str) -> None:
    multiworld = world.multiworld
    player = world.player
    opt = world.opt
    random = world.random

    base_out_path = os.path.join(output_directory, multiworld.get_out_file_name_base(player))
    patch_path = base_out_path + MK64DeltaPatch.patch_file_ending     # AP_<seed>_<player>.apmk64
    rom_out_path = base_out_path + MK64DeltaPatch.result_file_ending  # AP_<seed>_<player>.z64

    rom = Rom(get_base_rom_path())
    try:
        # PATCHING START

        # Patch save file
        save_id = hashlib.md5((multiworld.seed_name + multiworld.player_name[player]).encode()).digest()[:8]
        locked_courses = 0xFFFF << 16 - opt.locked_courses & 0xFFFF
        drift = ((opt.drift == ShuffleDriftAbilities.option_off and 0xAAAA) or
                 (opt.drift == ShuffleDriftAbilities.option_free_drift and 0x5555) or 0)
        blues = 0b11 if opt.special_boxes else 0
        kart_unlocks = sum(1 << Items.item_name_groups["Karts"].index(kart) for kart in world.starting_karts)
        tires_off_road = 0 if opt.traction else 0xFF
        tires_winter = 0 if opt.traction else 0xFF
        locked_cups = 0b1110    # only Mushroom Cup starts unlocked
        switches = 0 if opt.fences else 0b1111
        misc_byte = 1 if opt.box_respawning else 0b101  # game_clear (initially 0), connected status bit (always 1)

        # Pack to bytes ordered to the basepatch's SaveData struct bitfields
        rom.write_bytes(Addr.SAVE,       save_id)  # replaces DATETIME pseudo-hash in basepatch
        rom.write_int16(Addr.SAVE + 0x8, locked_courses)
        rom.write_int16(Addr.SAVE + 0xA, drift)
        rom.write_byte(Addr.SAVE + 0xF,  blues)
        rom.write_byte(Addr.SAVE + 0x14, kart_unlocks)
        rom.write_byte(Addr.SAVE + 0x15, tires_off_road)
        rom.write_byte(Addr.SAVE + 0x16, tires_winter)
        rom.write_byte(Addr.SAVE + 0x17, (locked_cups << 4) | switches)
        rom.write_byte(Addr.SAVE + 0x19, misc_byte)

        # Patch Locked Item Clusters
        initial_locked_clusters = bytearray(Addr.SAVE_LOCKED_ITEM_CLUSTERS_SIZE)
        for c, cluster in enumerate(world.shuffle_clusters):
            if cluster:
                initial_locked_clusters[c // 8] |= 1 << c % 8
        rom.write_bytes(Addr.SAVE_LOCKED_ITEM_CLUSTERS, initial_locked_clusters)

        # Patch player name and multiworld seed_name for later ROM authentication with the client
        player_name_bytes = multiworld.player_name[player].encode("utf-8")
        if len(player_name_bytes) > 64:
            raise ValueError(f"Player name {multiworld.player_name[player]} was longer than the 64 byte expectation.")
        rom.write_bytes(Addr.PLAYER_NAME, [0] * Addr.PLAYER_NAME_SIZE)
        rom.write_bytes(Addr.PLAYER_NAME, player_name_bytes)
        seed_name_bytes = multiworld.seed_name.encode("utf-8")
        if len(seed_name_bytes) > 20:
            raise ValueError(f"Multiworld.seed_name {multiworld.seed_name} was longer than the 20 byte expectation.")
        rom.write_bytes(Addr.SEED_NAME, [0] * Addr.SEED_NAME_SIZE)
        rom.write_bytes(Addr.SEED_NAME, seed_name_bytes)

        # Patch game settings
        mirror_courses = 0
        for i in range(16):
            if random.random() < opt.mirror_chance:
                mirror_courses |= 1 << i
        two_lap_mapping = {0: 0, 1: 0x8000, 2: 0x0100, 3: 0x8100}
        two_lap_courses = two_lap_mapping[opt.two_lap_courses]
        rom.write_byte(Addr.TWO_PLAYER_POWERS, opt.two_player)
        rom.write_byte(Addr.GAME_MODE, opt.mode)
        rom.write_byte(Addr.FREE_MINI_TURBO, opt.drift == ShuffleDriftAbilities.option_free_mini_turbo)
        rom.write_int16(Addr.MIRROR_COURSES, mirror_courses)
        rom.write_int16(Addr.TWO_LAP_COURSES, two_lap_courses)
        rom.write_byte(Addr.SHUFFLE_RAILINGS, opt.railings)
        rom.write_byte(Addr.FEATHER_AVAILABLE, opt.feather)
        rom.write_byte(Addr.CONSISTENT_ITEM_BOXES, opt.consistent)
        if opt.consistent == ConsistentItemBoxes.option_on:
            rom.write_bytes(Addr.SAVE_IDENTIFIED_ITEM_BOXES, [0xFF] * Addr.SAVE_IDENTIFIED_ITEM_BOXES_SIZE)
        rom.write_int16(Addr.ENGINE_CLASSES, opt.low_engine)
        rom.write_int16(Addr.ENGINE_CLASSES + 2, opt.middle_engine)
        rom.write_int16(Addr.ENGINE_CLASSES + 4, opt.high_engine)
        rom.write_byte(Addr.GENERATION_DONE, 1)
        rom.write_byte(Addr.GENERATION_LOCKED, 1)

        # Write custom course order
        if opt.course_order != CourseOrder.option_vanilla:
            course_ids = [0x8,  0x9, 0x6, 0xB,
                          0xA,  0x5, 0x1, 0x0,
                          0xE,  0xC, 0x7, 0x2,
                          0x12, 0x4, 0x3, 0xD]
            course_nameplate_ids = [0x4C, 0x50, 0x43, 0x59,
                                    0x54, 0x3E, 0x2A, 0x25,
                                    0x65, 0x5D, 0x48, 0x2F,
                                    0x75, 0x3A, 0x34, 0x61]
            for i, c in enumerate(world.course_order):
                rom.write_byte(Addr.COURSE_IDS + 2 * i + 1, course_ids[c])
                rom.write_byte(Addr.COURSE_NAMEPLATES + 20 * math.floor(1.25 * i), course_nameplate_ids[c])

        # Patch optional fixes
        # The basepatch may already have the music fix set, so we set either case here just in case
        rom.write_byte(Addr.RESULTS_MUSIC_REPETITIONS, 0x2 if opt.fix_music else 0x40)

        # Write items, and marked unavailable locations as checked
        initial_unchecked_locs = bytearray(Addr.SAVE_UNCHECKED_LOCATIONS_SIZE)
        for i, loc in enumerate(multiworld.get_locations(player)):
            if loc.address is None:  # Skip Victory Event Location
                continue
            local_loc_id = loc.address - ID_BASE
            initial_unchecked_locs[local_loc_id // 8] |= 1 << local_loc_id % 8
            # Write items
            addr = Addr.ITEMS + Addr.ITEM_SIZE * local_loc_id
            rom.write_byte(addr + 1, loc.item.classification & 0b111)  # 0=FILLER,1=PROGRESSION,2=USEFUL,4=TRAP
            rom.write_byte(addr + 2, i)  # pickup_id, used by the game to reference player name and item name
            pickup_item_name = unicodedata.normalize("NFKD", loc.item.name)\
                                          .encode("ascii", "ignore")[:Addr.ITEM_NAME_SIZE]
            rom.write_bytes(Addr.PICKUP_ITEM_NAMES + i * Addr.ITEM_NAME_SIZE, pickup_item_name)
            if loc.item.player == player:
                rom.write_byte(addr, loc.item.code - ID_BASE)  # local_id (0 to 211)
            else:
                rom.write_byte(addr, 0xFF)  # local_id of 0xFF indicates nonlocal item
                pickup_player_name = unicodedata.normalize("NFKD", multiworld.player_name[loc.item.player])\
                                                .encode("ascii", "ignore")[:Addr.ASCII_PLAYER_NAME_SIZE]
                rom.write_bytes(Addr.PICKUP_PLAYER_NAMES + Addr.ASCII_PLAYER_NAME_SIZE * i, pickup_player_name)
        rom.write_bytes(Addr.SAVE_UNCHECKED_LOCATIONS, initial_unchecked_locs)

        # Update CRC
        rom.write_bytes(0x10, rom.calculate_crc_6102())

        # PATCHING DONE

        rom.write_to_file(rom_out_path)
        patch = MK64DeltaPatch(patch_path, player, multiworld.player_name[player], patched_path=rom_out_path)
        patch.write()
        print("Done generating one patch.")
    except Exception as e:
        print("Mario Kart 64 failed its generate_output routine.")
        raise e
    finally:  # TODO: Maybe find out unlink() too.
        if os.path.exists(rom_out_path):
            os.unlink(rom_out_path)


def get_base_rom_path(file_name: str = "") -> str:
    host_settings = settings.get_settings()
    # Utils.get_options()
    if not file_name:
        file_name = host_settings["mk64_options"]["rom_file"]
    if not os.path.exists(file_name):
        file_name = Utils.user_path(file_name)
    return file_name


def get_base_rom_bytes(file_name: str = "") -> bytes:
    base_rom_bytes = getattr(get_base_rom_bytes, "base_rom_bytes", None)
    if not base_rom_bytes:
        file_name = get_base_rom_path(file_name)
        base_rom_bytes = bytes(open(file_name, "rb").read())
        basemd5 = hashlib.md5()
        basemd5.update(base_rom_bytes)
        if MK64DeltaPatch.hash != basemd5.hexdigest():
            raise Exception('Supplied base ROM does not match known MD5 for US release of Mario Kart 64. '
                            'Please provide the correct ROM version.')
        get_base_rom_bytes.base_rom_bytes = base_rom_bytes
    return base_rom_bytes


class MK64DeltaPatch(APDeltaPatch):
    hash = "3a67d9986f54eb282924fca4cd5f6dff"
    patch_file_ending = ".apmk64"
    result_file_ending = ".z64"
    game = "Mario Kart 64"

    @classmethod
    def get_source_data(cls) -> bytes:
        return get_base_rom_bytes()


class Rom:
    def __init__(self, file):
        self.orig_buffer = None
        base_rom_bytes = get_base_rom_bytes(file)
        patch_bytes = pkgutil.get_data(__name__, "data/mk64-ap-basepatch.bsdiff")
        self.buffer = bytearray(bsdiff4.patch(base_rom_bytes, patch_bytes))

    def read_bit(self, address: int, bit_number: int) -> bool:
        bitflag = (1 << bit_number)
        return (self.buffer[address] & bitflag) != 0

    def read_byte(self, address: int) -> int:
        return self.buffer[address]

    def read_bytes(self, startaddress: int, length: int) -> bytes:
        return self.buffer[startaddress:startaddress + length]

    def write_byte(self, address: int, value: int):
        self.buffer[address] = value

    def write_bytes(self, startaddress: int, values: list | bytes | bytearray):
        self.buffer[startaddress:startaddress + len(values)] = values

    def write_int16(self, address, value: int):
        value = value & 0xFFFF
        self.write_bytes(address, [(value >> 8) & 0xFF, value & 0xFF])

    def write_int16s(self, startaddress, values: list):
        for i, value in enumerate(values):
            self.write_int16(startaddress + (i * 2), value)

    def write_int24(self, address, value: int):
        value = value & 0xFFFFFF
        self.write_bytes(address, [(value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF])

    def write_int24s(self, startaddress, values: list):
        for i, value in enumerate(values):
            self.write_int24(startaddress + (i * 3), value)

    def write_int32(self, address, value: int):
        value = value & 0xFFFFFFFF
        self.write_bytes(address, [(value >> 24) & 0xFF, (value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF])

    def write_int32s(self, startaddress, values: list):
        for i, value in enumerate(values):
            self.write_int32(startaddress + (i * 4), value)

    def write_to_file(self, file):
        with open(file, 'wb') as outfile:
            outfile.write(self.buffer)

    def read_from_file(self, file):
        with open(file, 'rb') as stream:
            self.buffer = bytearray(stream.read())

    # Adapted from espeon65536's version in oot/data/crc.py
    def calculate_crc_6102(self):

        t1 = t2 = t3 = t4 = t5 = t6 = 0xF8CA4DDC
        u32 = 0xFFFFFFFF

        m1 = self.read_bytes(0x1000, 0x100000)
        words = struct.unpack(f'>{len(m1)//4}I', m1)

        m2 = self.read_bytes(0x750, 0x100)
        words2 = struct.unpack(f'>{len(m2)//4}I', m2)

        for d, d2 in zip(words, itertools.cycle(words2)):
            # keep t2 and t6 in u32 for comparisons; others can wait to be truncated
            if ((t6 + d) & u32) < t6:
                t4 += 1

            t6 = (t6+d) & u32
            t3 ^= d
            shift = d & 0x1F
            r = ((d << shift) | (d >> (32 - shift)))
            t5 += r

            if t2 > d:
                t2 ^= r & u32
            else:
                t2 ^= t6 ^ d

            t1 += t5 ^ d

        crc0 = (t6 ^ t4 ^ t3) & u32
        crc1 = (t5 ^ t2 ^ t1) & u32

        return struct.pack('>II', crc0, crc1)
