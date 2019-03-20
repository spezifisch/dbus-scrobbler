import click

import dbus
import datetime
import logging
import coloredlogs
from mpris2 import get_players_uri, Player
from legacy_scrobbler import LegacyScrobbler, Listen


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


class PlayerState:
    def __init__(self, legacy_scrobbler):
        self.legacy_scrobbler = legacy_scrobbler
        self.listen = None

        self.logger = logging.getLogger("PlayerState")
        coloredlogs.install(level="DEBUG", logger=self.logger)

    def submit_maybe(self):
        now = utc_now()

        if self.listen and self.listen.eligible_for_scrobbling(now):
            self.logger.info("submitting song")
            self.legacy_scrobbler.add_listens([self.listen])
            self.listen = None

    def tick(self):
        self.submit_maybe()

    def state_playing(self):
        if self.listen:
            self.logger.info("now playing {}, submitting in {} s".format(self.listen, self.listen.required_play_time))
            self.legacy_scrobbler.send_nowplaying(self.listen)

    def state_paused(self):
        self.submit_maybe()
        # TODO do it properly
        self.listen = None

    def state_stopped(self):
        self.submit_maybe()
        self.listen = None

    def set_metadata(self, data):
        try:
            listen = Listen(utc_now(),
                            artist_name=data["artist_name"],
                            track_title=data["track_title"],
                            album_title=data.get("album_title"),
                            length=round(int(data["length_us"]) / 1e6),
                            tracknumber=data.get("tracknumber")
                            )
        except KeyError:
            print("key missing")
            return
        except TypeError:
            print("no last_metadata")
            return
        except ValueError:
            print("bad length")
            return

        self.listen = listen


class Scrobbler:
    MPRIS_TO_FIELD = {
        "xesam:artist": "artist_name",
        "xesam:title": "track_title",
        "xesam:album": "album_title",
        "mpris:length": "length_us",
        "xesam:trackNumber": "tracknumber",
    }

    def __init__(self, **kwargs):
        self.logger = logging.getLogger("dbus-scrobbler")
        coloredlogs.install(level="DEBUG", logger=self.logger)

        self.players = []

        self.connect_to_all_players()

        self.legacy_scrobbler = LegacyScrobbler(kwargs["service_name"],
                                                kwargs["username"], kwargs["hashed_password"],
                                                kwargs["handshake_url"])

        self.player_state = PlayerState(self.legacy_scrobbler)

    def connect_to_all_players(self):
        for uri in get_players_uri():
            p = Player(dbus_interface_info={'dbus_uri': uri})
            p.PropertiesChanged = self.properties_changed_cb
            self.players.append(p)

    def tick(self):
        self.player_state.tick()
        self.legacy_scrobbler.tick()

        # keep timer running
        return True

    def properties_changed_cb(self, *args, **kwargs):
        if len(args) < 2:
            return

        data = args[1]
        if "PlaybackStatus" in data:
            self.playback_status_cb(data["PlaybackStatus"])
        if "Metadata" in data:
            self.metadata_cb(data["Metadata"])

    def playback_status_cb(self, data):
        self.logger.debug("playback_status_cb: {}".format(data))

        if data == "Playing":
            self.player_state.state_playing()
        elif data == "Paused":
            self.player_state.state_paused()
        elif data == "Stopped":
            self.player_state.state_stopped()

    def metadata_cb(self, data):
        d = {}
        for key, new_key in self.MPRIS_TO_FIELD.items():
            if key in data:
                value = data[key]
                if isinstance(value, dbus.Array):
                    value = ", ".join([str(x) for x in value])
                else:
                    value = str(value)

                d[new_key] = value

        # self.logger.debug("metadata_cb: {}".format(data))
        self.player_state.set_metadata(d)


@click.command()
@click.argument("config_file")
def run(config_file):
    from dbus.mainloop.glib import DBusGMainLoop
    import gi.repository.GLib
    from gi.repository import GObject
    import yaml

    dbus_loop = DBusGMainLoop(set_as_default=True)

    # load config
    with open(config_file, "r") as file:
        config = yaml.safe_load(file)

    scrobbler = Scrobbler(**config)

    GObject.timeout_add_seconds(1, scrobbler.tick)
    mloop = gi.repository.GLib.MainLoop()
    mloop.run()


if __name__ == "__main__":
    run()
