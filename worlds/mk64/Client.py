import unicodedata
import logging

from typing import TYPE_CHECKING, Optional, Set

from .Locations import ID_BASE
from .Rom import Addr

from NetUtils import ClientStatus
import worlds._bizhawk as bizhawk
from worlds._bizhawk.client import BizHawkClient

if TYPE_CHECKING:
    from worlds._bizhawk.context import BizHawkClientContext

logger = logging.getLogger("Client")


class MarioKart64Client(BizHawkClient):
    game = "Mario Kart 64"
    system = "N64"
    patch_suffix = ".apmk64"
    local_checked_locations: Set[int]
    rom_slot_name: Optional[str]

    def __init__(self) -> None:
        super().__init__()
        self.local_checked_locations = set()
        self.rom_slot_name = None
        self.unchecked_locs: bytearray = bytearray([0xFF] * Addr.SAVE_UNCHECKED_LOCATIONS_SIZE)
        self.displacements = None
        self.engine_class_changed = False

    async def validate_rom(self, ctx: "BizHawkClientContext") -> bool:
        from CommonClient import logger

        try:
            # Check if ROM is some version of MK64 patched with the Archipelago basepatch
            game_name = ((await bizhawk.read(ctx.bizhawk_ctx, [(0x20, 0x10, "ROM")]))[0]).decode("ascii")
            if game_name != "MK64 ARCHIPELAGO":
                return False

            # Check if we can read the slot name. Doing this here instead of set_auth as a protection against
            # validating a ROM where there's no slot name to read.
            try:
                read_state = await bizhawk.read(ctx.bizhawk_ctx, [(Addr.PLAYER_NAME, Addr.PLAYER_NAME_SIZE, "ROM"),
                                                                  (Addr.SAVE, 4, "ROM"),
                                                                  (Addr.ENGINE_CLASSES, 6, "ROM")])
                player_name = read_state[0].rstrip(b"\xFE").decode("utf-8")
                hash_seed_hex = read_state[1].hex().upper()
                self.rom_slot_name = f"{player_name}_{hash_seed_hex}"
            except UnicodeDecodeError:
                logger.info("Could not read slot name from ROM. Are you sure this ROM matches this client version?")
                return False
        except UnicodeDecodeError:
            return False
        except bizhawk.RequestFailedError:
            return False  # Should verify on the next pass

        ctx.game = self.game
        ctx.items_handling = 0b001  # Client handles items sent from other worlds, but not from your own world.
        ctx.command_processor.commands["low_engine_class"] = cmd_low_engine_class
        ctx.command_processor.commands["middle_engine_class"] = cmd_middle_engine_class
        ctx.command_processor.commands["high_engine_class"] = cmd_high_engine_class
        ec = read_state[2]
        self.displacements = [ec[0] << 8 | ec[1],
                              ec[2] << 8 | ec[3],
                              ec[4] << 8 | ec[5]]
        ctx.want_slot_data = False
        return True

    async def set_auth(self, ctx: "BizHawkClientContext") -> None:
        ctx.auth = self.rom_slot_name

    async def game_watcher(self, ctx: "BizHawkClientContext") -> None:
        # from BizHawkClient import RequestFailedError, bizhawk_write, bizhawk_guarded_write, bizhawk_read

        try:
            # Read Game State
            read_state = await bizhawk.read(ctx.bizhawk_ctx, [
                (Addr.GAME_STATUS_BYTE, 1, "RDRAM"),
                (Addr.NUM_ITEMS_RECEIVED, 1, "RDRAM"),
                (Addr.LOCATIONS_UNCHECKED, Addr.SAVE_UNCHECKED_LOCATIONS_SIZE, "RDRAM")])

            if not read_state[0][0]:  # first bit is always 1 to indicate valid connection
                return

            game_clear = (read_state[0][0] >> 1) & 1
            num_received_items = read_state[1][0]
            locs_state = read_state[2]

            # Receive item if we have one
            if num_received_items < len(ctx.items_received):
                receive_item = ctx.items_received[num_received_items]
                local_id = receive_item.item - ID_BASE
                receive_player = unicodedata.normalize("NFKD", ctx.player_names[receive_item.player])\
                                            .encode("ascii", "ignore")[:Addr.ASCII_PLAYER_NAME_SIZE]
                receive_item_name = unicodedata.normalize("NFKD", ctx.item_names.lookup_in_game(receive_item.item))\
                                               .encode("ascii", "ignore")[:Addr.ITEM_NAME_SIZE]
                await bizhawk.guarded_write(ctx.bizhawk_ctx,
                    [(Addr.RECEIVE_ITEM_ID, local_id.to_bytes(1, "big"), "RDRAM"),
                        (Addr.RECEIVE_CLASSIFICATION, receive_item.flags.to_bytes(1, "big"), "RDRAM"),
                        (Addr.RECEIVE_PLAYER_NAME, receive_player, "RDRAM"),
                        (Addr.RECEIVE_ITEM_NAME, receive_item_name, "RDRAM")],
                    [(Addr.RECEIVE_ITEM_ID, [0xFF], "RDRAM")])

            # Check for new locations to send
            new_locs = list()
            for i, byte in enumerate(locs_state):
                if byte != self.unchecked_locs[i]:
                    for j in range(8):
                        if byte & 1 << j != self.unchecked_locs[i] & 1 << j:
                            new_locs.append(ID_BASE + 8 * i + j)
                    self.unchecked_locs[i] = byte

            # Send new locations
            if new_locs is not None:
                await ctx.send_msgs([{
                    "cmd": "LocationChecks",
                    "locations": new_locs
                }])

            # Send new engine class displacements
            if self.engine_class_changed:
                self.engine_class_changed = False
                cc = self.displacements
                displacement_bytes = [(cc[0] >> 8) & 0xFF, cc[0] & 0xFF,
                                      (cc[1] >> 8) & 0xFF, cc[1] & 0xFF,
                                      (cc[2] >> 8) & 0xFF, cc[2] & 0xFF]
                await bizhawk.write(ctx.bizhawk_ctx, [(Addr.ENGINE_CLASSES_RAM, displacement_bytes, "RDRAM")])

            # Send game clear
            if not ctx.finished_game and game_clear:
                await ctx.send_msgs([{
                    "cmd":    "StatusUpdate",
                    "status": ClientStatus.CLIENT_GOAL
                }])

        except bizhawk.RequestFailedError:
            # Exit handler and return to main loop to reconnect.
            pass


def padl(x: int) -> str:
    return ("  " if x < 100 else "") + str(x)


def padr(x: int) -> str:
    return str(x) + ("  " if x < 100 else "")


def set_engine_class(ctx, engine_class: int, displacement: str, range_min: int, range_max: int) -> bool:
    if ctx.game != "Mario Kart 64":
        logger.warning("This command can only be used while playing Mario Kart 64.")
        return False
    cc = ctx.client_handler.displacements
    if not displacement:
        logger.info("              Current    Wiggle Room    Full Allowed Range")
        logger.info(f"  Low:     {padl(cc[0])}cc           35 – {padr(cc[1] - 25)}             35 – 150")
        logger.info(f"  Middle: {padl(cc[1])}cc        {padl(cc[0] + 25)} – {padr(cc[2] - 25)}             60 – 175")
        logger.info(f"  High:     {padl(cc[2])}cc        {padl(cc[1] + 25)} – 200             85 – 200")
        logger.info("Include a number to change that engine class. "
                    "Adjacent classes may change to maintain 25cc spacing.")
        return False
    try:
        displacement_number = int(''.join(filter(str.isdigit, displacement)))
    except ValueError:
        logger.warning(f"Unable to parse '{displacement}'. Enter a number between {range_min} and {range_max}.")
        return False
    if not (range_min <= displacement_number <= range_max):
        logger.warning(f"Could not find engines in that size. Enter a number between {range_min} and {range_max}.")
        return False
    cc[engine_class] = displacement_number
    logger.info(f"{['Low', 'Middle', 'High'][engine_class]} Engine Class set to {displacement_number}cc.")
    ctx.client_handler.engine_class_changed = True
    return True


def cmd_low_engine_class(self, displacement: str = ""):
    """Sets the low engine class (50cc is standard)."""
    if not set_engine_class(self.ctx, 0, displacement, 35, 150):
        return
    cc = self.ctx.client_handler.displacements
    if cc[0] + 25 > cc[1]:
        logger.warning(f"Adjacent Middle Engine Class increased from {cc[1]}cc to {cc[0] + 25}cc.")
        self.ctx.client_handler.displacements[1] = cc[0] + 25
    if cc[0] + 50 > cc[2]:
        logger.warning(f"Adjacent High Engine Class increased from {cc[2]}cc to {cc[0] + 50}cc.")
        self.ctx.client_handler.displacements[2] = cc[0] + 50


def cmd_middle_engine_class(self, displacement: str = ""):
    """Sets the middle engine class (100cc is standard)."""
    if not set_engine_class(self.ctx, 1, displacement, 60, 175):
        return
    cc = self.ctx.client_handler.displacements
    if cc[1] - 25 < cc[0]:
        logger.warning(f"Adjacent Low Engine Class decreased from {cc[0]}cc to {cc[1] - 25}cc.")
        self.ctx.client_handler.displacements[0] = cc[1] - 25
    if cc[1] + 25 > cc[2]:
        logger.warning(f"Adjacent High Engine Class increased from {cc[2]}cc to {cc[1] + 25}cc.")
        self.ctx.client_handler.displacements[2] = cc[1] + 25


def cmd_high_engine_class(self, displacement: str = ""):
    """Sets the high engine class (150cc is standard)."""
    if not set_engine_class(self.ctx, 2, displacement, 85, 200):
        return
    cc = self.ctx.client_handler.displacements
    if cc[2] - 50 < cc[0]:
        logger.warning(f"Adjacent Low Engine Class decreased from {cc[0]}cc to {cc[2] - 50}cc.")
        self.ctx.client_handler.displacements[0] = cc[2] - 50
    if cc[2] - 25 < cc[1]:
        logger.warning(f"Adjacent Middle Engine Class decreased from {cc[1]}cc to {cc[2] - 25}cc.")
        self.ctx.client_handler.displacements[1] = cc[2] - 25
