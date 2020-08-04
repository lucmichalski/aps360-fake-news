#!/usr/bin/env python
#
#  main.py
#  Fake News Classifier.
#
#  Created on 2020-07-30.
#

import argparse
import logging
import os
import random

import torch
import torchtext

import src.preprocessing as preprocessing
import src.training as training
import src.utils as utils


def main():
    # yapf: disable
    parser = argparse.ArgumentParser(description='Fake News Classifier')
    # Modes
    parser.add_argument('--init', action='store_true', default=False,
                        help='perform initialization')
    parser.add_argument('--train', action='store_true', default=False,
                        help='train the model')
    parser.add_argument('--test', action='store_true', default=False,
                        help='test the model (must either train or load a model)')
    parser.add_argument('--plot', action='store_true', default=False,
                        help='plot training data (must either train or have existing training data)')
    # Options
    parser.add_argument('-b', '--batch-size', type=int, default=64, metavar='N',
                        help='input batch size for training (default: 64)')
    parser.add_argument('--data-loader', type=str, default='BatchLoader',
                        help='data loader to use (default: "BatchLoader")')
    parser.add_argument('--dataset', type=str, default='FakeRealNews',
                        help='dataset to use (default: "FakeRealNews")')
    parser.add_argument('-e', '--epochs', type=int, default=10,
                        help='number of epochs to train (default: 10)')
    parser.add_argument('--lr', '--learning-rate', type=float, default=1e-4,
                        help='learning rate (default: 1e-4)')
    parser.add_argument('-l', '--load', type=int, metavar='EPOCH',
                        help='load a model and its training data')
    parser.add_argument('--loss', type=str, default='BCEWithLogitsLoss',
                        help='loss function (default: "BCEWithLogitsLoss")')
    parser.add_argument('--model', type=str, default='FakeNewsNet',
                        help='model architecture to use (default: "FakeNewsNet")')
    parser.add_argument('-s', '--sample-size', type=int, metavar='N',
                        help='limit sample size for training')
    parser.add_argument('--seed', type=int, default=0,
                        help='random seed (default: 0)')
    parser.add_argument('--save', action='store_true', default=True,
                        help='save model checkpoints and training data (default: True)')
    parser.add_argument('--no-save', dest='save', action='store_false')
    args = parser.parse_args()
    # yapf: enable

    # Configure logger
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger('matplotlib').setLevel(logging.WARNING)

    # Exit if no mode is specified
    if not args.init and not args.train and not args.test and not args.plot:
        logging.error(
            'No mode specified. Please choose one of "--init", "--train", "--test", "--plot".'
        )
        exit(1)
    # Exit on "--load" if run directory not found
    if (args.load is not None or
        (args.plot
         and not args.train)) and not os.path.isdir(utils.get_path(args)):
        logging.error(
            'Could not find directory for current configuration {}'.format(
                utils.get_path(args)))
        exit(1)
    # Exit on "--test" without "--train" or "--load"
    if args.test and not (args.train or args.load is not None):
        logging.error(
            'Cannot run "--test" without a model. Try again with either "--train" or "--load".'
        )
        exit(1)

    # Setup run directory
    if args.save and not (args.init
                          and not (args.train or args.test or args.plot)):
        utils.save_config(args)
        path = utils.get_path(args) + '/output.log'
        os.makedirs(os.path.dirname(path), exist_ok=True)
        logging.getLogger().addHandler(logging.FileHandler(path))

    # Set random seeds
    random.seed(args.seed)
    torch.manual_seed(args.seed)

    # Variable declarations
    training_data = None

    # Perform initialization
    if args.init or args.train or args.test:
        # Determine which dataset to use
        dataset = utils.get_dataset(args)

        # Preload the dataset
        dataset.load()
        # Load GloVe vocabulary
        glove = torchtext.vocab.GloVe(name='6B', dim=50)

        # Get preprocessed vectors
        samples = preprocessing.get_samples(dataset, glove, args.init)
        random.shuffle(samples)

    # Setup for train, test
    if args.train or args.test:
        # Select data loader to use
        DataLoader = utils.get_data_loader(args)

        # Split samples
        split_ratio = [.6, .2, .2]
        trainset, validset, testset = list(
            DataLoader.splits(samples, split_ratio))
        if args.sample_size is not None:  # limit samples used in training
            trainset = trainset[:args.sample_size]
            validset = validset[:int(args.sample_size * split_ratio[1] /
                                     split_ratio[0])]

        # Get data loaders
        train_loader, valid_loader, test_loader = [
            DataLoader(split, batch_size=args.batch_size)
            for split in [trainset, validset, testset]
        ]

        # Create the model
        model = utils.get_model(glove, args)

        # Load a model
        if args.load is not None:
            utils.load_model(args.load, model, args)

    # Run "--train"
    if args.train:
        training_data = training.train(model, train_loader, valid_loader, args)

    # Run "--test"
    if args.test:
        if args.train or args.load is not None:
            criterion = utils.get_criterion(args.loss)
            acc, loss = training.evaluate(model, test_loader, criterion)
            logging.info('Testing accuracy: {:.4%}, loss: {:.6f}'.format(
                acc, loss))
        else:
            logging.error('No model loaded for testing')
            exit(1)

    # Run "--plot"
    if args.plot:
        if training_data is None:
            training_data = utils.load_training_data(args, allow_missing=False)

        logging.info('Plotting training data')
        training.plot(training_data)


if __name__ == '__main__':
    main()
