import time
import sys
import threading

from fullmetalmadda import FMM_IRCConnectionManager

from .PyDojo import on_private_msg, on_channel_msg

CONN = FMM_IRCConnectionManager("voting_bot.cfg")


def irc_loop():
    # Create the new IRC connection using the supplied config file name
    conn = CONN

    while(True):
        message = conn.get_message()
        if message is None:
            continue
        print(message.data['message'])

        if(conn.quit_sent):
            time.sleep(3)
            conn.disconnect()
            sys.exit(0)

        if message.data['type'] == 'PRIVMSG':
            if message.data['channel'] == '#:PRIVATE:#':
                on_private_msg(
                    message.data['target'],
                    message.data['message'],
                )
            else:
                on_channel_msg(
                    message.data['target'],
                    message.data['channel'],
                    message.data['message'],
                )


if __name__ == "__main__":
    threading.Thread(target=irc_loop).start()
