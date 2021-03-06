import wandb
from gym.spaces import Box, Discrete

from RL import argparser as p
from RL import register_algo
from RL.agents.console_print_agent import ConsolePrintAgent
from RL.agents.episode_type_control_agent import EpisodeTypeControlAgent
from RL.agents.exp_buff_agent import ExperienceBufferAgent
from RL.agents.model_copy_agent import ModelCopyAgent
from RL.agents.reward_scaling_agent import RewardScalingAgent
from RL.agents.sac_agent import SACAgent
from RL.agents.sac_discrete_agent import SACDiscreteAgent
from RL.agents.seeding_agent import SeedingAgent
from RL.agents.simple_render_agent import SimpleRenderAgent
from RL.agents.stats_recording_agent import StatsRecordingAgent

from .standard_wrap_algo import StandardEnvWrapAlgo


class SAC(StandardEnvWrapAlgo):
    def setup(self):
        args = p.parse_args()
        self.register_agent(SeedingAgent("SeedingAgent", self, args.seed))
        self.register_agent(RewardScalingAgent(
            "RewardScaler", self, reward_scaling=args.reward_scaling, cost_scaling=args.cost_scaling))

        self.register_agent(EpisodeTypeControlAgent('EpisodeTypeController', self, args.eval_mode,
                                                    args.min_explore_steps, args.exploit_freq))  # type: EpisodeTypeControlAgent

        if not args.eval_mode:
            exp_buff_agent = self.register_agent(ExperienceBufferAgent(
                "ExpBuffAgent", self, args.nsteps, args.gamma, args.cost_gamma, args.exp_buff_len, None, not args.no_ignore_done_on_timelimit))
        else:
            exp_buff_agent = None

        convs = list(filter(lambda x: x != [0], [
                     args.conv1, args.conv2, args.conv3]))
        action_space = self.manager.env.action_space

        if isinstance(action_space, Box):
            Agent_class = SACAgent
        elif isinstance(action_space, Discrete):
            Agent_class = SACDiscreteAgent
        else:
            raise ValueError(f'Unsupported Action Space {action_space}')

        sac_agent = self.register_agent(Agent_class('SACAgent', self, convs, args.hiddens,
                                                    args.train_freq, args.mb_size, args.gamma, args.nsteps,
                                                    args.td_clip, args.grad_clip, args.lr, args.a_lr, args.eval_mode, args.min_explore_steps, None if args.eval_mode else exp_buff_agent.experience_buffer, args.sac_alpha, args.fix_alpha))  # type: SACAgent

        if not args.eval_mode:
            self.register_agent(ModelCopyAgent('TargetNetCopier1', self, sac_agent.q1,
                                               sac_agent.target_q1, 1, args.polyak, args.min_explore_steps))
            self.register_agent(ModelCopyAgent('TargetNetCopier2', self, sac_agent.q2,
                                               sac_agent.target_q2, 1, args.polyak, args.min_explore_steps))

        self.register_agent(StatsRecordingAgent("StatsRecorder", self, reward_scaling=args.reward_scaling, cost_scaling=args.cost_scaling, record_unscaled=args.record_unscaled,
                                                gamma=args.gamma, cost_gamma=args.cost_gamma, record_undiscounted=not args.record_discounted, frameskip=self.frameskip))  # type: StatsRecordingAgent

        self.register_agent(ConsolePrintAgent("ConsolePrinter", self, lambda: {
            'Steps': self.manager.num_steps,
            'Episodes': self.manager.num_episodes,
            'Len': self.manager.num_episode_steps,
            'R': wandb.run.history.row['Episode/Reward'],
            'R(100)': wandb.run.history.row['Average/RPE (Last 100)'],
            'loss': wandb.run.history.row['SAC/Loss'],
            'v': wandb.run.history.row['SAC/Value'],
            'alpha': wandb.run.history.row['SAC/Alpha'],
            'entropy': wandb.run.history.row['SAC/Entropy']
        }, lambda: {
            'Total Steps': self.manager.num_steps,
            'Total Episodes': self.manager.num_episodes,
            'Average RPE': wandb.run.history.row['Average/RPE'],
            'Average CPE': wandb.run.history.row['Average/CPE']
        }))

        if not args.no_render:
            self.register_agent(SimpleRenderAgent("SimpleRenderAgent", self))


register_algo('SAC', SAC)
