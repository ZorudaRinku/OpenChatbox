from .time_token import TimeToken
from .date_token import DateToken
from .cpu_token import CpuToken
from .ram_token import RamToken
from .gpu_token import GpuToken
from .timezone_token import TimezoneToken
from .window_token import WindowToken
from .distro_token import DistroToken
from .cpu_speed_token import CpuSpeedToken
from .gpu_speed_token import GpuSpeedToken
from .ram_gb_token import RamGbToken
from .wm_token import WmToken
from .de_token import DeToken
from .uptime_token import UptimeToken
from .battery_token import BatteryToken
from .disk_token import DiskToken
from .network_token import NetworkToken
from .ping_token import PingToken
from .cpu_temp_token import CpuTempToken
from .gpu_temp_token import GpuTempToken
from .now_playing_token import NowPlayingToken
from .artist_token import ArtistToken
from .song_token import SongToken
from .volume_token import VolumeToken
from .utc_token import UtcToken
from .countdown_token import CountdownToken
from .session_token import SessionToken
from .weather_token import WeatherToken
from .heartrate_token import HeartrateToken
from .heartrate_emote_token import HeartrateEmoteToken
from .egg_token import EggToken
from .random_token import RandomToken
from .song_progress_token import SongProgressToken
from .song_progress_bar_token import SongProgressBarToken
from .twitch_followers_token import TwitchFollowersToken
from .twitch_viewers_token import TwitchViewersToken
from .vrc_status_token import VrcStatusToken
from .vrc_status_message_token import VrcStatusMessageToken
from .vrc_pronouns_token import VrcPronounsToken
from .vrc_friends_online_token import VrcFriendsOnlineToken
from .vrc_friends_total_token import VrcFriendsTotalToken
from .vrc_friends_in_instance_token import VrcFriendsInInstanceToken
from .vrc_time_in_world_token import VrcTimeInWorldToken
from .vrc_world_token import VrcWorldToken
from .vrc_instance_users_token import VrcInstanceUsersToken
from .vrc_instance_group_token import VrcInstanceGroupToken
from .vrc_region_token import VrcRegionToken
from .vrc_session_length_token import VrcSessionLengthToken
from .vrc_worlds_hopped_token import VrcWorldsHoppedToken
from .vrc_notifications_token import VrcNotificationsToken
from .blankline_token import BlanklineToken


ALL_TOKENS = [ArtistToken, BatteryToken, BlanklineToken, CountdownToken,
              CpuSpeedToken, CpuTempToken,
              CpuToken, DateToken, DeToken, DiskToken, DistroToken,
              EggToken, GpuSpeedToken, GpuTempToken, GpuToken,
              HeartrateEmoteToken, HeartrateToken, NetworkToken, NowPlayingToken, PingToken,
              RandomToken, RamGbToken, RamToken, SongProgressBarToken, SongProgressToken,
              SessionToken, SongToken, TimeToken, TimezoneToken, UptimeToken,
              TwitchFollowersToken, TwitchViewersToken,
              UtcToken,
              VrcStatusToken, VrcStatusMessageToken, VrcPronounsToken,
              VrcFriendsOnlineToken, VrcFriendsTotalToken,
              VrcFriendsInInstanceToken, VrcWorldToken, VrcTimeInWorldToken,
              VrcInstanceUsersToken, VrcInstanceGroupToken, VrcRegionToken,
              VrcSessionLengthToken, VrcWorldsHoppedToken, VrcNotificationsToken,
              VolumeToken, WeatherToken, WindowToken, WmToken]
