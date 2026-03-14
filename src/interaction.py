import time
from asyncio import sleep
import fluxer

from .commands import pop_cooldown

class Interaction:
    def __init__(self, author: int, callback, expire_after = 5 * 60):
        self.author = author
        self.callback = callback
        self.expire_time = time.monotonic() + expire_after

    def __repr__(self):
        return f"Interaction({self.author}, expire_time={self.expire_time})"

class Interactions:
    instance: Interactions

    def __init__(self):
        Interactions.instance = self
        self.react_interactions: dict[int, list[Interaction]] = {}

    def clean_old(self):
        now = time.monotonic()
        pop_keys = []
        for mid, interactions in self.react_interactions.items():
            to_remove = []
            for i, interaction in enumerate(interactions):
                if interaction.expire_time < now:
                    to_remove.append(i)
            to_remove.reverse()
            for index in to_remove:
                interactions.pop(index)
            if not interactions:
                pop_keys.append(mid)
        for key in pop_keys:
            self.react_interactions.pop(key)

    def add_interaction(self, message_id: int, interaction: Interaction):
        if message_id in self.react_interactions:
            self.react_interactions[message_id].append(interaction)
            return

        self.react_interactions[message_id] = [interaction]

    def __repr__(self):
        return f"Interactions({self.react_interactions!r})"

    async def wait_claim_after(self, timeout: int, message_id: int, message_author: int) -> bool:
        pop_cooldown(message_author)
        await sleep(timeout)
        if message_id in self.react_interactions:
            self.react_interactions.pop(message_id)
            return True
        return False

    async def interact(self, message_id: int, author: int, args) -> bool:
        self.clean_old()
        ret = False

        if interactions := self.react_interactions.get(message_id, None):
            for interaction in interactions:
                if interaction.author == author:
                    res = await interaction.callback(*args)
                    if isinstance(res, dict) and res["pop"] and message_id in self.react_interactions:
                        self.react_interactions.pop(message_id)
                    ret = True
        return ret

    def delete_interaction(self, message_id: int):
        if message_id in self.react_interactions:
            self.react_interactions.pop(message_id)

message_reactions: dict[tuple[int, int], list[str]] = {}
async def remove_reaction(message: fluxer.Message, emoji: str, user: fluxer.User | int | None = None):
    await message.remove_reaction(emoji, user or "@me")

    if user:
        user_id = user.id if (not isinstance(user, int)) and user is not None else user
        if (message.id, user_id) in message_reactions:
            message_reactions[(message.id, user_id)].remove(emoji)

            if not message_reactions[(message.id, user_id)]:
                message_reactions.pop((message.id, user_id))