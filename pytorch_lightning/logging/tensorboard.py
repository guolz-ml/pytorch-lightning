import os
from warnings import warn

import torch
from pkg_resources import parse_version
from torch.utils.tensorboard import SummaryWriter

from .base import LightningLoggerBase, rank_zero_only


class TensorboardLogger(LightningLoggerBase):
    r"""Log to local file system in Tensorboard format

    Implemented using :class:`torch.utils.tensorboard.SummaryWriter`. Logs are saved to
    `os.path.join(save_dir, name, version)`

    :example:

    .. code-block:: python

        logger = TensorboardLogger("tb_logs", name="my_model")
        trainer = Trainer(logger=logger)
        trainer.train(model)

    :param str save_dir: Save directory
    :param str name: Experiment name. Defaults to "default".
    :param int version: Experiment version. If version is not specified the logger inspects the save
        directory for existing versions, then automatically assigns the next available version.
    :param \**kwargs: Other arguments are passed directly to the :class:`SummaryWriter` constructor.


    """

    def __init__(self, save_dir, name="default", version=None, **kwargs):
        super().__init__()
        self.save_dir = save_dir
        self._name = name
        self._version = version if version is not None else None

        self._experiment = None
        self.kwargs = kwargs

    @property
    def experiment(self):
        """The underlying :class:`torch.utils.tensorboard.SummaryWriter`.

        :rtype: torch.utils.tensorboard.SummaryWriter
        """
        if self._experiment is not None:
            return self._experiment

        root_dir = os.path.join(self.save_dir, self.name)
        os.makedirs(root_dir, exist_ok=True)
        log_dir = os.path.join(root_dir, str(self.version))
        self._experiment = SummaryWriter(log_dir=log_dir, **self.kwargs)
        return self._experiment

    @rank_zero_only
    def log_hyperparams(self, params):
        if parse_version(torch.__version__) < parse_version("1.3.0"):
            warn(
                f"Hyperparameter logging is not available for Torch version {torch.__version__}. "
                "Skipping log_hyperparams. Upgrade to Torch 1.3.0 or above to enable "
                "hyperparameter logging"
            )
            return
        self.experiment.add_hparams(hparam_dict=vars(params))

    @rank_zero_only
    def log_metrics(self, metrics, step_idx=None):
        for k, v in metrics.items():
            if isinstance(v, torch.Tensor):
                v = v.item()
            self.experiment.add_scalar(k, v, step_idx)

    @rank_zero_only
    def save(self):
        self.experiment.flush()

    @rank_zero_only
    def finalize(self, status):
        self.save()

    @property
    def name(self):
        return self._name

    @property
    def version(self):
        if self._version is None:
            self._version = self._get_next_version()
        return self._version

    def _get_next_version(self):
        root_dir = os.path.join(self.save_dir, self.name)
        existing_versions = [
            int(d) for d in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, d)) and d.isdigit()
        ]
        if len(existing_versions) == 0:
            return 0
        else:
            return max(existing_versions) + 1