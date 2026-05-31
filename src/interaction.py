import time
from asyncio import sleep
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .service import Platform, Context


class Interaction:
    def __init__(self, author: int, callback, expire_after = 5 * 60, pop_after_use = True):
        self.author = author
        self.callback = callback
        self.expire_time = time.monotonic() + expire_after
        self.pop_after_use = pop_after_use

    def __repr__(self):
        return f"Interaction({self.author}, expire_time={self.expire_time})"

class Interactions:
    instance: Interactions

    def __init__(self):
        Interactions.instance = self
        self.react_interactions: dict[tuple[int, Platform], list[Interaction]] = {}

    def clean_old(self):
        now = time.monotonic()
        pop_keys: list[tuple[int, Platform]] = []
        for (message_id, platform), interactions in self.react_interactions.items():
            to_remove = []
            for i, interaction in enumerate(interactions):
                if interaction.expire_time < now:
                    to_remove.append(i)
            to_remove.reverse()
            for index in to_remove:
                interactions.pop(index)
            if not interactions:
                pop_keys.append((message_id, platform))
        for key in pop_keys:
            self.react_interactions.pop(key)

    def add_interaction(self, context: Context, interaction: Interaction):
        if (context.id, context.platform) in self.react_interactions:
            self.react_interactions[context.id, context.platform].append(interaction)
            return

        self.react_interactions[context.id, context.platform] = [interaction]

    def __repr__(self):
        return f"Interactions({self.react_interactions!r})"

    async def wait_claim_after(self, timeout: int, message_id: int, platform: Platform) -> bool:
        await sleep(timeout)
        if message_id in self.react_interactions:
            self.react_interactions.pop((message_id, platform))
            return True
        return False

    async def interact(self, context: Context, author: int, args) -> bool:
        self.clean_old()
        ret = False

        if interactions := self.react_interactions.get((context.id, context.platform), None):
            for interaction in interactions:
                if interaction.author == author:
                    await interaction.callback(*args)
                    if interaction.pop_after_use:
                        del interactions
                        if not self.react_interactions[context.id, context.platform]:
                            self.react_interactions.pop((context.id, context.platform))
                    ret = True
        return ret

    def delete_interaction(self, context: Context):
        if (context.id, context.platform) in self.react_interactions:
            self.react_interactions.pop((context.id, context.platform))
