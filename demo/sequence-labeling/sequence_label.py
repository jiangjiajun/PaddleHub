#   Copyright (c) 2019 PaddlePaddle Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Finetuning on sequence labeling task."""

import argparse
import ast

import paddle.fluid as fluid
import paddlehub as hub

# yapf: disable
parser = argparse.ArgumentParser(__doc__)
parser.add_argument("--num_epoch", type=int, default=3, help="Number of epoches for fine-tuning.")
parser.add_argument("--use_gpu", type=ast.literal_eval, default=True, help="Whether use GPU for finetuning, input should be True or False")
parser.add_argument("--learning_rate", type=float, default=5e-5, help="Learning rate used to train with warmup.")
parser.add_argument("--weight_decay", type=float, default=0.01, help="Weight decay rate for L2 regularizer.")
parser.add_argument("--warmup_proportion", type=float, default=0.0, help="Warmup proportion params for warmup strategy")
parser.add_argument("--max_seq_len", type=int, default=512, help="Number of words of the longest seqence.")
parser.add_argument("--batch_size", type=int, default=32, help="Total examples' number in batch for training.")
parser.add_argument("--checkpoint_dir", type=str, default=None, help="Directory to model checkpoint")
args = parser.parse_args()
# yapf: enable.

if __name__ == '__main__':
    # Step1: load Paddlehub ERNIE pretrained model
    module = hub.Module(name="ernie")
    inputs, outputs, program = module.context(
        trainable=True, max_seq_len=args.max_seq_len)

    # Step2: Download dataset and use SequenceLabelReader to read dataset
    dataset = hub.dataset.MSRA_NER()
    reader = hub.reader.SequenceLabelReader(
        dataset=dataset,
        vocab_path=module.get_vocab_path(),
        max_seq_len=args.max_seq_len)

    # Step3: construct transfer learning network
    with fluid.program_guard(program):
        label = fluid.layers.data(
            name="label", shape=[args.max_seq_len, 1], dtype='int64')
        seq_len = fluid.layers.data(name="seq_len", shape=[1], dtype='int64')

        # Use "sequence_output" for token-level output.
        sequence_output = outputs["sequence_output"]

        # Setup feed list for data feeder
        # Must feed all the tensor of ERNIE's module need
        # Compared to classification task, we need add seq_len tensor to feedlist
        feed_list = [
            inputs["input_ids"].name, inputs["position_ids"].name,
            inputs["segment_ids"].name, inputs["input_mask"].name, label.name,
            seq_len
        ]
        # Define a sequence labeling finetune task by PaddleHub's API
        seq_label_task = hub.create_seq_label_task(
            feature=sequence_output,
            labels=label,
            seq_len=seq_len,
            num_classes=dataset.num_labels)

        # Select a finetune strategy
        strategy = hub.AdamWeightDecayStrategy(
            weight_decay=args.weight_decay,
            learning_rate=args.learning_rate,
            warmup_strategy="linear_warmup_decay",
        )

        # Setup runing config for PaddleHub Finetune API
        config = hub.RunConfig(
            use_cuda=args.use_gpu,
            num_epoch=args.num_epoch,
            batch_size=args.batch_size,
            checkpoint_dir=args.checkpoint_dir,
            strategy=strategy)

        # Finetune and evaluate model by PaddleHub's API
        # will finish training, evaluation, testing, save model automatically
        hub.finetune_and_eval(
            task=seq_label_task,
            data_reader=reader,
            feed_list=feed_list,
            config=config)
