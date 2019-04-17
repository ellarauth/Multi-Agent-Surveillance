from typing import Dict
import math
import random
from enum import Enum
import vectormath as vmath
import json_tricks as jt

import simulation
from .environment import Map
from .agent import Agent, AgentID, GuardAgent, IntruderAgent
from .util import Position


class World:
    """
    Main class that manages the whole simulation
    """

    # amount of times `on_tick` is called per second
    TICK_RATE = 20
    # time elapsed for each call to `on_tick`
    TIME_PER_TICK = 1.0 / TICK_RATE

    def __init__(self, map: Map):
        self.map: Map = map
        self.agents: Dict[AgentID, Agent] = dict()

        self.noises: List['simulation.world.NoiseEvent'] = []
        # to keep track of past noise events
        self.old_noises: List['simulation.world.NoiseEvent'] = []

        # to keep track of how many ticks have passed:
        self.time_ticks = 0

    def save_map(self, name) -> None:
        data = {'map': self.map.to_dict()}

        filename = f'saves/{name}.map.json'
        with open(filename, mode='w') as file:
            jt.dump(data, file, indent=4)

    def save_agents(self, name) -> None:
        data = {'agents': [agent.__class__.__name__ for ID, agent in self.agents.items()]}

        filename = f'saves/{name}.agents.json'
        with open(filename, mode='w') as file:
            jt.dump(data, file, indent=4)

    def to_file(self, name, save_agents=True) -> None:
        self.save_map(name)
        if save_agents:
            self.save_agents(name)

    @classmethod
    def load_map(cls, name) -> 'World':
        filename = f'saves/{name}.map.json'
        with open(filename, mode='r') as file:
            data = jt.load(file)

        m = Map.from_dict(data['map'])
        return World(m)

    def load_agents(self, name) -> None:
        filename = f'saves/{name}.agents.json'
        with open(filename, mode='r') as file:
            data = jt.load(file)

        # add agents
        import importlib
        for agent_name in data['agents']:
            # get class by string
            agent_class = getattr(importlib.import_module("ai.agents"), agent_name)
            # and add it to the world
            self.add_agent(agent_class)

    @classmethod
    def from_file(cls, name, load_agents=True) -> 'World':
        world = cls.load_map(name)
        if load_agents:
            world.load_agents(name)
        return world

    def add_agent(self, agent_type):
        agent = agent_type()
        self.agents[agent.ID] = agent

    def add_noise(self, noise: 'NoiseEvent'):
        noise.time = self.time_ticks
        self.noises.append(noise)

    @property
    def guards(self):
        return {ID: agent for ID, agent in self.agents.items() if isinstance(agent, GuardAgent)}

    @property
    def intruders(self):
        return {ID: agent for ID, agent in self.agents.items() if isinstance(agent, IntruderAgent)}

    def transmit_message(self, message):
        self.agents[message.target]._message_queue_in.append(message)

    def _collision_check(self):
        def collision_point(x, y):
            x, y = int(math.floor(x)), int(math.floor(y))
            if self.map.is_wall(x, y):
                return vmath.Vector2(x, y) + (0.5, 0.5)
            else:
                return None
            
        def circle_collision(x, y, r=0.5):
                x, y = int(math.floor(x)), int(math.floor(y))
                if self.map.is_wall(x, y):
                    center = vmath.Vector2(x, y) + (0.5, 0.5)
                    if (agent.location - center).length < (r + width / 2):
                        return center + (agent.location - center).as_length(r + width / 2)


        for ID, agent in self.agents.items():
            # do a quick bounds check first so they stay on the map
            if agent.location.x < 0:
                agent.location.x = 0
            if agent.location.y < 0:
                agent.location.y = 0
            if agent.location.x >= self.map.width:
                agent.location.x = self.map.width - 0.01
            if agent.location.y >= self.map.height:
                agent.location.y = self.map.height - 0.01

            # get some values we'll need
            width = agent._width
            x = agent.location.x
            y = agent.location.y

            # offset vector for collision resolution
            push = vmath.Vector2(0, 0)

            # left
            collision = collision_point(x - width / 2, y)
            if collision is not None:
                push.x += collision.x + (0.5 + width / 2) - agent.location.x
                agent._has_collided |= True
            # right
            collision = collision_point(x + width / 2, y)
            if collision is not None:
                push.x += collision.x - (0.5 + width / 2) - agent.location.x
                agent._has_collided |= True
            # bottom
            collision = collision_point(x, y - width / 2)
            if collision is not None:
                push.y += collision.y + (0.5 + width / 2) - agent.location.y
                agent._has_collided |= True
            # top
            collision = collision_point(x, y + width / 2)
            if collision is not None:
                push.y += collision.y - (0.5 + width / 2) - agent.location.y
                agent._has_collided |= True

            # and apply resolution vector
            agent.location += push

            collision = circle_collision(x - width / 2, y - width / 2)
            if collision is not None:
                agent.location.x = collision.x
                agent.location.y = collision.y
                agent._has_collided |= True

            collision = circle_collision(x - width / 2, y + width / 2)
            if collision is not None:
                agent.location.x = collision.x
                agent.location.y = collision.y
                agent._has_collided |= True

            collision = circle_collision(x + width / 2, y - width / 2)
            if collision is not None:
                agent.location.x = collision.x
                agent.location.y = collision.y
                agent._has_collided |= True

            collision = circle_collision(x + width / 2, y + width / 2)
            if collision is not None:
                agent.location.x = collision.x
                agent.location.y = collision.y
                agent._has_collided |= True

    def _capture_check(self) -> bool:
        """
        return: Whether or not all the intruders have been captured
        """
        # see if any intruders will be captured now
        for ID_intruder, intruder in self.intruders.items():
            for ID_guard, guard in self.guards.items():
                # still needs check for whether intruder is in sight
                if (intruder.location - guard.location).length < 0.5:
                    intruder.is_captured = True
                    intruder.on_captured()

        # check if all intruders are captured
        return all((intruder.is_captured for ID, intruder in self.intruders.items()))

    def _target_check(self) -> bool: 
        """
        return: Whether or not all of the intruders have reached the target
        """
        # see if any intruders will reach the target now
        for ID_intruder, intruder in self.intruders.items():
            # somehow agents don't get closer to the target than 0.7 or 0.64
            if (intruder.location - intruder.target).length < 0.5: 
                if intruder.ticks_in_target == 0.0:
                    if (intruder.ticks_since_target * self.TIME_PER_TICK) >= 3.0 or intruder.times_visited_target == 0.0:
                        intruder.times_visited_target += 1.0
                        
                    intruder.ticks_since_target = 0.0
                    
                intruder.ticks_in_target += 1.0
            
            else:    
                if intruder.ticks_in_target > 0.0:
                    intruder.ticks_since_target += 1.0
                    intruder.ticks_in_target = 0.0
                            
                elif intruder.ticks_since_target > 0.0:
                    intruder.ticks_since_target += 1.0
            
            # win type 1: the intruder has been in the target area for 3 seconds
            if (intruder.ticks_in_target * self.TIME_PER_TICK) >= 3.0:
                intruder.reached_target = True
                intruder.on_reached_target()
            
            # win type 2: the intruder has visited the target area twice with at least 3 seconds inbetween
            elif intruder.times_visited_target >= 2.0:
                intruder.reached_target = True

        # check if all intruders have reached the target
        return all((intruder.reached_target for ID, intruder in self.intruders.items()))
    
    def setup(self):
        for ID, agent in self.agents.items():
            agent.setup(world=self)

    def tick(self) -> bool:
        """
        Execute one tick / frame
        return: Whether or not the simulation is finished
        """
        # reset noise list
        self.old_noises.extend(self.noises)
        self.noises = []
        # emit random noise
        self.emit_random_noise()

        # find all events for every agent and then run the agent code
        for ID, agent in self.agents.items():
            # check if we can see any other agents
            visible_agents = []
            for other_ID, other_agent in self.agents.items():
                if other_ID == ID:
                    continue
                d = other_agent.location - agent.location
                angle_diff = abs((-math.degrees(math.atan2(d.y, d.x)) + 90 - agent.heading + 180) % 360 - 180)
                if (d.length <= agent.view_range and angle_diff <= agent.view_angle) \
                        or d.length <= 1.5:
                    # create a new `AgentView` event
                    visible_agents.append(simulation.vision.AgentView(other_agent))
            
            # and run the agent code
            agent.tick(seen_agents=visible_agents)
        self._collision_check()

        for ID, agent in self.agents.items():
            agent.on_noise(self.noises);


        all_captured = self._capture_check()

        if all_captured:
            # we're done
            print('The guards won!')
            return True
        
        all_reached_target = self._target_check()
        if all_reached_target:
            # we're done
            print('The intruders won!')
            return True


        # and up the counter
        self.time_ticks += 1

        if all_captured:
            # we're done
            return True
        # keep going...
        return False

    def emit_random_noise(self):
        # Rate parameter for one 25m^2 is 0.1 per minute -> divide by 60 to get the events per second
        # Scale up the rate parameter to map size 6*(map_size/25)*2=64 (amount of 25m^2 squares in the map)
        # I know, that the map size should be dynamic
#        event_rate = 0.1
        event_rate = 10
        random_events_per_second = (event_rate / 60) * (self.map.size[0] * self.map.size[1] / 25)
        chance_to_emit = random_events_per_second * self.TIME_PER_TICK
        if random.uniform(0, 1) < chance_to_emit:
            # emit an event here
            x = random.randint(0, self.map.size[0] - 1)
            y = random.randint(0, self.map.size[1] - 1)

            noise_event = NoiseEvent(Position(x, y))
            self.add_noise(noise_event)


class MarkerType(Enum):
    """The different types of markers used for indirect communication"""
    RED = 1
    GREEN = 2
    BLUE = 3
    YELLOW = 4
    MAGENTA = 5


class Marker:
    def __init__(self, type: MarkerType, location: Position):
        self.type = type
        self.location = location


class Message:
    """Encapsulates a single message"""

    def __init__(self, source, target, message: str) -> None:
        self.source: 'AgentID' = source
        self.target: 'AgentID' = target
        self.message: str = message


class NoiseEvent:
    """Encapsulates a single noise event"""

    def __init__(self, location: Position, source=None, radius=5/2) -> None:
        self.time = 0
        self.location = location
        self.source = source
        self.radius = radius

    def perceived_angle(self, target_pos: Position):
        """
        Calculates the perceived angle towards the noise from the perspective of the `target_pos`
        This also adds the uncertainty as described in the booklet
        """
        ...
