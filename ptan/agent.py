"""
Agent is something which converts states into actions and has state
"""
import copy
import numpy as np
import torch
import torch.nn.functional as F
from torch.autograd import Variable

from . import actions


class BaseAgent:
    """
    Abstract Agent interface
    """
    def initial_state(self):
        """
        Should create initial empty state for the agent. It will be called for the start of the episode
        :return: Anything agent want to remember
        """
        return None

    def __call__(self, states, agent_states):
        """
        Convert observations and states into actions to take
        :param states: list of environment states to process
        :param agent_states: list of states with the same length as observations
        :return: tuple of actions, states
        """
        assert isinstance(states, list)
        assert isinstance(agent_states, list)
        assert len(agent_states) == len(states)

        raise NotImplementedError


def default_states_preprocessor(states):
    """
    Convert list of states into numpy array
    :param states: list of numpy arrays with states
    :return: numpy array with the states
    """
    if len(states) == 1:
        np_states = np.expand_dims(states[0], 0)
    else:
        np_states = np.array(states)
    return np_states


def float32_preprocessor(states):
    return np.array(states, dtype=np.float32)


class DQNAgent(BaseAgent):
    """
    DQNAgent is a memoryless DQN agent which calculates Q values
    from the observations and  converts them into the actions using action_selector
    """
    def __init__(self, dqn_model, action_selector, cuda=False, preprocessor=default_states_preprocessor,
                 cuda_device_id=None):
        self.dqn_model = dqn_model
        self.action_selector = action_selector
        self.preprocessor = preprocessor
        self.cuda = cuda
        self.cuda_device_id = cuda_device_id

    def __call__(self, states, agent_states=None):
        if agent_states is None:
            agent_states = [None] * states.shape[0]
        if self.preprocessor is not None:
            states = self.preprocessor(states)
        v = Variable(torch.from_numpy(states))
        if self.cuda:
            v = v.cuda(device_id=self.cuda_device_id)
        q_v = self.dqn_model(v)
        q = q_v.data.cpu().numpy()
        actions = self.action_selector(q)
        return actions, agent_states


class TargetNet:
    """
    Wrapper around model which provides copy of it instead of trained weights
    """
    def __init__(self, model):
        self.model = model
        self.target_model = copy.deepcopy(model)

    def sync(self):
        self.target_model.load_state_dict(self.model.state_dict())

    def alpha_sync(self, alpha):
        """
        Blend params of target net with params from the model
        :param alpha:
        """
        assert isinstance(alpha, float)
        assert 0.0 < alpha <= 1.0
        state = self.model.state_dict()
        tgt_state = self.target_model.state_dict()
        for k, v in state.items():
            tgt_state[k] = tgt_state[k] * alpha + (1 - alpha) * v
        self.target_model.load_state_dict(tgt_state)


class PolicyAgent(BaseAgent):
    """
    Policy agent gets action probabilities from the model and samples actions from it
    """
    # TODO: unify code with DQNAgent, as only action selector is differs.
    def __init__(self, model, action_selector=actions.ProbabilityActionSelector(), cuda=False, apply_softmax=False, preprocessor=default_states_preprocessor):
        self.model = model
        self.action_selector = action_selector
        self.cuda = cuda
        self.apply_softmax = apply_softmax
        self.preprocessor = preprocessor

    def __call__(self, states, agent_states=None):
        """
        Return actions from given list of states
        :param states: list of states
        :return: list of actions
        """
        if agent_states is None:
            agent_states = [None] * states.shape[0]
        if self.preprocessor is not None:
            states = self.preprocessor(states)
        v = Variable(torch.from_numpy(states))
        if self.cuda:
            v = v.cuda()
        probs_v = self.model(v)
        if self.apply_softmax:
            probs_v = F.softmax(probs_v)
        probs = probs_v.data.cpu().numpy()
        actions = self.action_selector(probs)
        return np.array(actions), agent_states

