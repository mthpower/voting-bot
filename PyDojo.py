from enum import Enum
from collections import defaultdict

FILE = "ideas.txt"

class state(Enum):
    IDEAS = "collecting ideas"
    DISPLAY = "showing ideas"
    VOTE1 = "approval vote"
    VOTE2 = "selection vote"

current_state = state.IDEAS
ideas = []
channel = "#ldnpydojo"
vote1_counts = defaultdict(set)
vote2_counts = {}

def on_channel_msg(user, channel, msg):
    if current_state is VOTE1:
        try:
            num = int(msg)
        except ValueError:
            return
        vote1_counts[num].add(user)
    if current_state is VOTE2:
        try:
            num = int(msg)
        except ValueError:
            return
        vote2_counts[user] = num

def on_private_msg(user, msg):
    global current_state
    msg = msg.strip()
    if not msg:
        return
    if " " in msg:
        command, arg = msg.split(' ', 1)
    else:
        command = msg
        arg = None
    if command == "display":
        load_ideas()
        for num, idea in enumerate(ideas):
            send_msg(channel, f"{num}. {idea}")
        current_state = state.DISPLAY
    if command == "vote":
        if current_state is state.DISPLAY:
            start_vote1()
        if current_state is state.VOTE1:
            start_vote2()
        send_msg(user, f"Ok, beginning {current_state.value}")
    if command == 'idea':
        save_idea(arg)
        send_msg(user, 'Thanks for the idea!')
    else:
        send_msg(user, "I don't understand")

def start_vote1():
    global current_state
    current_state = state.VOTE1
    

def start_vote2():
    global current_state
    current_state = state.VOTE2
    winners = []
    for num, idea in enumerate(ideas):
        votes = len(vote1_counts[num])
        winners.append((votes, idea))
    winners.sort(reverse=True)
    del winners[3:]
    ideas[:] = [idea for votes, idea in winners]
    for num, (votes, idea) in enumerate(winners):
        send_msg(channel, f"{num}. {idea}")

def save_idea(idea):
    with open(FILE, "a") as f:
        print(idea, file=f)

def load_ideas():
    with open(FILE) as f:
        ideas[:] = f.read().splitlines()


def send_msg(target, msg):
    from voting_bot import CONN
    CONN.send('PRIVMSG', "#ldnpydojo", None, msg)

