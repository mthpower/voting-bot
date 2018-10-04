import time
import sys
import threading

from fullmetalmadda import FMM_IRCConnectionManager

CONN = FMM_IRCConnectionManager("voting_bot.cfg")


def irc_loop():
    # Create the new IRC connection using the supplied config file name
    conn = CONN

    while(True):
        message = conn.get_message()
        if message is None:
            continue

        if(conn.quit_sent):
            time.sleep(3)
            conn.disconnect()
            sys.exit(0)

        if message.data['type'] == 'PRIVMSG':
            if message.data['channel'] == '#:PRIVATE:#':
                on_private_message(message.data['target'],
                                   message.data['message'])
            else:
                on_channel_message(message.data['user'],
                                   message.data['channel'],
                                   message.data['messager'])

        time.sleep(1)

    conn.send(
        messagetype='PRIVMSG',
        target='#ldnpydojo',
        message='The message',
    )


if __name__ == "__main__":
    threading.Thread(target=irc_loop).start()
