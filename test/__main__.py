# Copyright (c) 2024 Josua Krause - All Rights Reserved
#
# THE CONTENTS OF THIS PROJECT ARE PROPRIETARY AND CONFIDENTIAL.
# UNAUTHORIZED COPYING, TRANSFERRING OR REPRODUCTION OF THE CONTENTS OF
# THIS PROJECT, VIA ANY MEDIUM IS STRICTLY PROHIBITED.
#
# The receipt or possession of the source code and/or any parts thereof does
# not convey or imply any right to use them for any purpose other than the
# purpose for which they were provided to you.
#
# The software is provided "AS IS", without warranty of any kind, express or
# implied, including but not limited to the warranties of merchantability,
# fitness for a particular purpose and non infringement. In no event shall the
# authors or copyright holders be liable for any claim, damages or other
# liability, whether in an action of contract, tort or otherwise, arising from,
# out of or in connection with the software or the use or other dealings in the
# software.
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the software.
"""A CLI tool for dividing up tests across executor nodes and merging their
results. This is used by github actions to have multiple runners."""
import argparse

from .mng import merge_results, split_tests


def parse_args_split_tests(parser: argparse.ArgumentParser) -> None:
    """
    Parses arguments for splitting tests across multiple executor nodes.

    Args:
        parser (argparse.ArgumentParser): The argument subparser.
    """
    parser.add_argument(
        "--filepath",
        default="test-results/results.xml",
        type=str,
        help="xml with previous test timings")
    parser.add_argument(
        "--total-nodes",
        type=int,
        help="number of test runner nodes")
    parser.add_argument(
        "--node-id",
        type=int,
        help="id of the current test runner node")


def parse_args_merge_results(parser: argparse.ArgumentParser) -> None:
    """
    Parses arguments for merging test results.

    Args:
        parser (argparse.ArgumentParser): The argument subparser.
    """
    parser.add_argument(
        "--dir",
        default="test-results",
        type=str,
        help=(
            "base test result folder. needs subfolder 'parts' "
            "containing all the xml files to join."))
    parser.add_argument(
        "--out-fname",
        type=str,
        help="output file of combined xml")


def parse_args() -> argparse.Namespace:
    """
    Parses the CLI arguments.

    Returns:
        argparse.Namespace: The parsed arguments.
    """
    parser = argparse.ArgumentParser(description="Test Utilities")
    subparser = parser.add_subparsers(title="Commands")

    def run_split_tests(args: argparse.Namespace) -> None:
        split_tests(
            filepath=args.filepath,
            total_nodes=args.total_nodes,
            cur_node=args.node_id)

    subparser_split_tests = subparser.add_parser("split")
    subparser_split_tests.set_defaults(func=run_split_tests)
    parse_args_split_tests(subparser_split_tests)

    def run_merge_results(args: argparse.Namespace) -> None:
        merge_results(
            base_folder=args.dir,
            out_filename=args.out_fname)

    subparser_merge_results = subparser.add_parser("merge")
    subparser_merge_results.set_defaults(func=run_merge_results)
    parse_args_merge_results(subparser_merge_results)
    return parser.parse_args()


def run() -> None:
    """Run the CLI tool."""
    args = parse_args()
    args.func(args)


if __name__ == "__main__":
    run()
