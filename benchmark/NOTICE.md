# Third-Party Notices

This benchmark workspace uses the MMLongBench-Doc dataset and adapts its
scoring logic.

## MMLongBench-Doc

MMLongBench-Doc: Benchmarking Long-context Document Understanding with
Visualizations

Repository: https://github.com/mayubo2333/MMLongBench-Doc  
Dataset: https://huggingface.co/datasets/yubo2333/MMLongBench-Doc

Authors: Yubo Ma, Yuhang Zang, Liangyu Chen, Meiqi Chen, Yizhu Jiao,
Xinze Li, Xinyuan Lu, Ziyu Liu, Yan Ma, Xiaoyi Dong, Pan Zhang,
Liangming Pan, Yu-Gang Jiang, Jiaqi Wang, Yixin Cao, and Aixin Sun.

The upstream README declares:

- Code license: Apache License 2.0.
- Dataset license: Creative Commons Attribution-NonCommercial 4.0
  International (CC BY-NC 4.0).

The scripts in this directory do not redistribute the MMLongBench-Doc PDFs or
question data. They download those files into `benchmark/data/`, which is
gitignored. Use of the dataset is for research and non-commercial purposes.

`benchmark/harness/scoring.py` is derived from the upstream Apache-2.0
`eval/eval_score.py` implementation, with small local changes for safer parsing
and script-oriented reuse.

## Citation

```bibtex
@misc{ma2024mmlongbenchdocbenchmarkinglongcontextdocument,
      title={MMLongBench-Doc: Benchmarking Long-context Document Understanding with Visualizations},
      author={Yubo Ma and Yuhang Zang and Liangyu Chen and Meiqi Chen and Yizhu Jiao and Xinze Li and Xinyuan Lu and Ziyu Liu and Yan Ma and Xiaoyi Dong and Pan Zhang and Liangming Pan and Yu-Gang Jiang and Jiaqi Wang and Yixin Cao and Aixin Sun},
      year={2024},
      eprint={2407.01523},
      archivePrefix={arXiv},
      primaryClass={cs.CV},
      url={https://arxiv.org/abs/2407.01523},
}
```
