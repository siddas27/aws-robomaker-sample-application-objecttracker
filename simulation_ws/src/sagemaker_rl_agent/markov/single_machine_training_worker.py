"""
This is single machine training worker. It starts a local training and stores the model in S3.
"""

import sys, os, signal

import argparse
import copy
import tensorflow as tf
# from markov.s3_boto_data_store import S3BotoDataStore, S3BotoDataStoreParameters
from rl_coach.base_parameters import TaskParameters, Frameworks
from rl_coach.utils import short_dynamic_import
import imp
import markov
from markov import utils
import markov.environments
import os
os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
os.environ["CUDA_VISIBLE_DEVICES"] = "1" #(or "1" or "2")

MARKOV_DIRECTORY = os.path.dirname(markov.__file__)
CUSTOM_FILES_PATH = "./custom_files"

if not os.path.exists(CUSTOM_FILES_PATH):
    os.makedirs(CUSTOM_FILES_PATH)


def write_frozen_graph(graph_manager, local_path):
    if not os.path.exists(local_path):
        os.makedirs(local_path)
    # TODO: Supports only PPO
    output_head = ['main_level/agent/main/online/network_1/ppo_head_0/policy']
    frozen = tf.graph_util.convert_variables_to_constants(graph_manager.sess, graph_manager.sess.graph_def, output_head)
    tf.train.write_graph(frozen, local_path, 'model.pb', as_text=False)
    print("Saved TF frozen graph!")


def start_graph(graph_manager: 'GraphManager', task_parameters: 'TaskParameters'):
    graph_manager.create_graph(task_parameters)

    # save randomly initialized graph
    graph_manager.save_checkpoint()

    # Start the training
    graph_manager.improve()

def save_graph(graph_manager: 'GraphManager', task_parameters: 'TaskParameters'):
    graph_manager.create_graph(task_parameters)

    # save randomly initialized graph
    write_frozen_graph(graph_manager, local_path='./rlmodel')




def add_items_to_dict(target_dict, source_dict):
    updated_task_parameters = copy.copy(source_dict)
    updated_task_parameters.update(target_dict)
    return updated_task_parameters

def should_stop_training_based_on_evaluation():
    return False

class SigTermHandler:
    def __init__(self, data_store):
        self.data_store = data_store
        signal.signal(signal.SIGINT, self.sigterm_exit)
        signal.signal(signal.SIGTERM, self.sigterm_exit)

    def sigterm_exit(self, signum, frame):
        self.data_store.unlock()
        sys.exit(0)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--markov-preset-file',
                        help="(string) Name of a preset file to run in Markov's preset directory.",
                        type=str,
                        default=os.environ.get("MARKOV_PRESET_FILE", "object_tracker.py"))
    parser.add_argument('-c', '--local_model_directory',
                        help='(string) Path to a folder containing a checkpoint to restore the model from.',
                        type=str,
                        default=os.environ.get("LOCAL_MODEL_DIRECTORY", "./checkpoint"))
    parser.add_argument('-n', '--num_workers',
                        help="(int) Number of workers for multi-process based agents, e.g. A3C",
                        default=1,
                        type=int)
    # parser.add_argument('--model-s3-bucket',
    #                     help='(string) S3 bucket where trained models are stored. It contains model checkpoints.',
    #                     type=str,
    #                     default=os.environ.get("MODEL_S3_BUCKET"))
    # parser.add_argument('--model-s3-prefix',
    #                     help='(string) S3 prefix where trained models are stored. It contains model checkpoints.',
    #                     type=str,
    #                     default=os.environ.get("MODEL_S3_PREFIX"))
    # parser.add_argument('--aws-region',
    #                     help='(string) AWS region',
    #                     type=str,
    #                     default=os.environ.get("ROS_AWS_REGION", "us-west-2"))
    parser.add_argument('--checkpoint-save-secs',
                        help="(int) Time period in second between 2 checkpoints",
                        type=int,
                        default=300)
    parser.add_argument('--save-frozen-graph',
                        help="(bool) True if we need to store the frozen graph",
                        type=bool,
                        default=True)

    args = parser.parse_args()

    if args.markov_preset_file:
        markov_path = imp.find_module("markov")[1]
        preset_location = os.path.join(markov_path, "presets", args.markov_preset_file)
        path_and_module = preset_location + ":graph_manager"
        graph_manager = short_dynamic_import(path_and_module, ignore_module_case=True)
        print("Using custom preset file from Markov presets directory!")
    else:
        raise ValueError("Unable to determine preset file")

    # TODO: support other frameworks
    task_parameters = TaskParameters(framework_type=Frameworks.tensorflow,
                                     checkpoint_save_secs=100)
    task_parameters.checkpoint_restore_path = args.local_model_directory
    task_parameters.checkpoint_save_dir = args.local_model_directory
    task_parameters.__dict__ = add_items_to_dict(task_parameters.__dict__, args.__dict__)

    # data_store_params_instance = S3BotoDataStoreParameters(bucket_name=args.model_s3_bucket,
    #                                                        s3_folder=args.model_s3_prefix,
    #                                                        checkpoint_dir=args.local_model_directory,
    #                                                        aws_region=args.aws_region)
    # data_store = S3BotoDataStore(data_store_params_instance)

    # sigterm_handler = SigTermHandler(data_store)

    # if args.save_frozen_graph:
    #     data_store.graph_manager = graph_manager

    # graph_manager.data_store_params = data_store_params_instance
    # graph_manager.data_store = data_store
    graph_manager.should_stop = should_stop_training_based_on_evaluation
    # start_graph(graph_manager=graph_manager, task_parameters=task_parameters)
    save_graph(graph_manager=graph_manager, task_parameters=task_parameters)



if __name__ == '__main__':
    main()
