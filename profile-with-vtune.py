#!/usr/bin/env python3

import argparse
import multiprocessing
import os
import re
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import pandas.api.types as pdty

VTUNE_PATH = "/opt/intel/oneapi/vtune/latest/bin64/vtune"
csv_delim = "^"
default_sampling_interval = 0.1
col_inst_event = "Hardware Event Count:INST_RETIRED.ANY"
col_clk_event = "Hardware Event Count:CPU_CLK_UNHALTED.THREAD"
col_src_func = "Function"
col_src_file = "Source File"
col_src_line = "Source Line"
col_cpu_time = "CPU Time"
correlation_cutoff = 0.80
num_bottlenecks = 3


def vtune_run_collect(collect_type: str, knobs: list, program_and_args: str, name_suffix: str, log_file: str):
    """
    :return: a list of string names for result directories
    """

    result_dir = f"vtune-raw-{collect_type}-{name_suffix}"

    knob_args = [("-knob " + k) for k in knobs]
    cmd = [
        VTUNE_PATH,
        "-start-paused",
        "-collect",
        collect_type,
        " ".join(knob_args),
        "-r ",
        result_dir,
        "--",
        program_and_args,
    ]

    cmd_str = " ".join(cmd)
    cmd_str += f" 2>&1 | tee -a {log_file}"
    print(f"Running: {cmd_str}")

    subprocess.run(cmd_str, shell=True, check=True)

    return result_dir


def vtune_run_report(report_type: str, result_dir: str, groupby: str, name_suffix: str):
    """
    :return: a list of string names of csv report files
    """

    csv_file = f"vtune-{report_type}-{groupby}-{name_suffix}.csv"
    # csv_file = f"vtune-{report_type}-{name_suffix}.csv"

    # special tweak. add gropuby function as well ahead of source-line
    if groupby == "source-line":
        groupby = f"function -group-by {groupby}"

    out_fh = open(csv_file, "w")

    # Stupid vtune appends hostname to result-dir on clusters like epee even with 1
    # node. 
    if not Path.is_dir(Path(result_dir)):
        hostname = socket.gethostname()
        result_dir = f"{result_dir}.{hostname}"
        csv_file = f"{csv_file}.{hostname}"
        assert Path.is_dir(Path(result_dir))

    cmd = [
        VTUNE_PATH,
        "-report",
        report_type,
        "-r",
        result_dir,
        "-format csv",
        f"-csv-delimiter {csv_delim} -group-by {groupby}",
    ]

    print(f"Running: {cmd} > {csv_file}")

    cmd_str = " ".join(cmd)

    subprocess.run(cmd_str, shell=True, check=True, stdout=out_fh)

    out_fh.close()

    return csv_file


class VTuneResult:
    def __init__(self, analysis: str, result_dir: str, csv_files: list):
        assert len(csv_files) >= 1
        self.analysis = analysis
        self.result_dir = result_dir
        self.csv_files = csv_files
        self.main_csv = csv_files[0]

    def _read_csv(self, csv_file:str = None):
        if not csv_file:
            csv_file = self.main_csv
        df = pd.read_csv(csv_file, sep=csv_delim)
        return df

    def _write_csv(self, df:pd.DataFrame, csv_file:str = None):
        if not csv_file:
            csv_file = self.main_csv
        df.to_csv(csv_file, sep=csv_delim, index=False)


class VTuneHotspotResult(VTuneResult):
    def __init__(self, analysis: str, result_dir: str, csv_files: list):
        assert analysis == "hotspots"
        VTuneResult.__init__(self, analysis, result_dir, csv_files)

    def _add_col_totals(self):
        # hotspots has total as 100% for some columns but not
        # for others
        df = self._read_csv()
        totals = pd.DataFrame(columns=df.columns)
        for col_name, col_data in df.iteritems():
            if pdty.is_numeric_dtype(col_data):
                totals[col_name] = col_data.sum()
            else:
                totals[col_name] = ["Total"]
        df = pd.concat([df, totals])
        self._write_csv(df)

    def _sort_by_cputime(self):
        # only sort the hotspot by function file
        df = self._read_csv()
        df.sort_values(col_cpu_time, ascending=False, inplace=True)
        self._write_csv(df)

    def compute_more_stats(self):
        self._add_col_totals()
        self._sort_by_cputime()


class VTuneCountersResult(VTuneResult):
    def __init__(self, analysis: str, result_dir: str, csv_files: list):
        assert analysis == "counters"
        VTuneResult.__init__(self, analysis, result_dir, csv_files)
        self.correlated_counters = []

    def _find_correlated_counters(self):
        # WARNING: this relies on there being either only 1 csv file or the first
        # csv file to contain the counter data
        df = self._read_csv()
        clk_cycles = df[col_clk_event]
        print(f"List of counters that correlate with {col_clk_event}")
        for col_name, col_data in df.iteritems():
            if not pdty.is_numeric_dtype(col_data):
                continue
            # if col_name != col_clk_event:
            if not re.search("CPU_CLK_UNHALTED", col_name):
                coeff = clk_cycles.corr(col_data)
                if coeff > correlation_cutoff:
                    counter_name = re.sub("Hardware Event Count:", "", col_name)
                    print(f"{counter_name} at {coeff}")
                    self.correlated_counters.append(counter_name)

    def _add_col_totals(self):
        for f in self.csv_files:
            df = self._read_csv(f)
            totals = pd.DataFrame(columns=df.columns)
            for col_name, col_data in df.iteritems():
                if pdty.is_numeric_dtype(col_data):
                    totals[col_name] = col_data.sum()
                else:
                    totals[col_name] = ["Total"]
            df = pd.concat([df, totals])
            self._write_csv(df, f)

    def _sort_by_clk(self):
        for f in self.csv_files:
            df = self._read_csv(f)
            df.sort_values(col_clk_event, ascending=False, inplace=True)
            self._write_csv(df, f)

    def compute_more_stats(self):
        # WARNING: Order of operations matters here. _add_col_totals affects the
        # column correlation so _find_correlated_counters should be called first
        self._find_correlated_counters()
        self._add_col_totals()
        self._sort_by_clk()
        # print(f"Counters correlated with Clock Cycles: {self.correlated_counters}")


def analyze_threads_vs_hotspots(threads: list, results: dict, name_suffix: str):
    table = {}
    for t in threads:
        df = results[t]._read_csv()
        table.setdefault("Threads", []).append(t)
        table.setdefault("Total_CPU_Time", []).append(df[col_cpu_time][0])
        rem = df[col_cpu_time][0]
        for i in range(1, num_bottlenecks + 1):
            prefix = f"Bottleneck_{i}"
            table.setdefault(f"{prefix}_Function", []).append(df[col_src_func][i])
            table.setdefault(f"{prefix}_Source_File", []).append(df[col_src_file][i])
            table.setdefault(f"{prefix}_CPU_seconds", []).append(df[col_cpu_time][i])
            frac = 100.0 * df[col_cpu_time][i] / df[col_cpu_time][0]
            table.setdefault(f"{prefix}_Percent_Time", []).append(frac)
            rem -= df[col_cpu_time][i]
            table.setdefault(f"Rem_Time_without_{prefix}", []).append(rem)

    main_df = pd.DataFrame(table)
    out_file = f"vtune-threads-vs-hotspots-{name_suffix}.csv"
    main_df.to_csv(out_file, sep=csv_delim, index=False)


def analyze_threads_vs_counters(threads: list, results: dict, name_suffix: str):

    table = {}
    # main_df['Threads'] = threads
    for t in threads:
        df = results[t]._read_csv()
        table.setdefault("Threads", []).append(t)
        table.setdefault("Total_Cycles", []).append(df[col_clk_event][0])
        table.setdefault("Total_Instructions", []).append(df[col_inst_event][0])
        table.setdefault("Cycle_Correlated_Events", []).append(",".join(results[t].correlated_counters))

        rem = df[col_clk_event][0]
        for i in range(1, num_bottlenecks + 1):
            prefix = f"Bottleneck_{i}"
            table.setdefault(f"{prefix}_Function", []).append(df[col_src_func][i])
            table.setdefault(f"{prefix}_Source_File", []).append(df[col_src_file][i])
            table.setdefault(f"{prefix}_Cycles", []).append(df[col_clk_event][i])
            frac = df[col_clk_event][i] / df[col_clk_event][0]
            table.setdefault(f"{prefix}_Cycles_Fraction", []).append(frac)
            rem -= df[col_clk_event][i]
            table.setdefault(f"Rem_Cycles_without_{prefix}", []).append(rem)

    main_df = pd.DataFrame(table)
    out_file = f"vtune-threads-vs-counters-{name_suffix}.csv"
    main_df.to_csv(out_file, sep=csv_delim, index=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="run Vtune analysis")

    parser.add_argument(
        "--analyze",
        "-analyze",
        "-a",
        default="hotspots",
        help="""
            Specify the analysis type for VTune.
            Possible values: hotspots, counters
            """,
    )

    parser.add_argument(
        "--threads", "-threads", "-t", default="1", help="Specify threads as a comma separated string, no spaces"
    )

    parser.add_argument("--tag", "-tag", default="", help="Specify a tag to identify this run")

    # TODO (amber): enable this option in the future
    # parser.add_argument(
    # "--save_result_dir", "-save_result_dir",
    # default = False,
    # help = "Save the vtune generated result directories. User responsible for cleanup"
    # )

    parser.add_argument(
        "--sampling_interval",
        "-sampling_interval",
        default=default_sampling_interval,
        help="""
            Specify sampling interval for hardware stack sampling in milliseconds.
            Applies only to counters 
            Choose such that the profiled section amounts to 100-1000 samples
            min value = 0.1 ms
            max value = 10000 ms
            Also, sampling interval for -sampling_mode=sw is fixed at 10ms by
            VTune. Use sw mode sampling to profile code that runs for > 1s
            """,
    )

    # parser.add_argument(
        # "--sampling_mode",
        # "-sampling_mode",
        # default=sampling_mode,
        # help="Specify sampling mode for stack sampling. Applies only to hotspots.  Possible values: hw, sw. Default: sw",
    # )

    parser.add_argument(
        "program_and_args", nargs="*", help="Specify an executable with args without the threads argument -t"
    )

    args = parser.parse_args()

    reports = []  # contains pairs of (reprot-type, group-by)
    knobs = []
    vtune_collect = ""
    if args.analyze == "hotspots":
        vtune_collect = "hotspots"
        reports = [
            # WARNING: Order matters. first report is used for further analysis
            ("hotspots", "function"),
            ("hotspots", "source-line"),
            ("top-down", "function"),
            ("callstacks", "callstack"),
        ]
    elif args.analyze == "counters":
        vtune_collect = "uarch-exploration"
        knobs.append(f"sampling-interval={args.sampling_interval}")
        reports = [
            # WARNING: Order matters. first report is used for further analysis
            ("hw-events", "function"),
            ("hw-events", "source-line"),
        ]

    assert vtune_collect != ""

    threads = args.threads.split(",")
    assert len(threads) >= 1

    results = {}
    timestamp = datetime.now().strftime("%Y-%m-%d_%H.%M.%S")
    prog_name = Path(args.program_and_args[0]).parts[-1]
    log_file = f"vtune-run-log-{prog_name}-{timestamp}.txt"
    for t in threads:
        name_suffix = f"{prog_name}-{args.tag}-t-{t}-{timestamp}"

        prog_and_args = " ".join(args.program_and_args) + f" -t {t}"
        vtune_raw_dir = vtune_run_collect(vtune_collect, knobs, prog_and_args, name_suffix, log_file)

        csv_files = []
        for (r, groupby) in reports:
            new_csv = vtune_run_report(r, vtune_raw_dir, groupby, name_suffix)
            csv_files.append(new_csv)

        if args.analyze == "counters":
            results[t] = VTuneCountersResult(args.analyze, vtune_raw_dir, csv_files)
            results[t].compute_more_stats()
        elif args.analyze == "hotspots":
            results[t] = VTuneHotspotResult(args.analyze, vtune_raw_dir, csv_files)
            results[t].compute_more_stats()
        else:
            assert False

    name_suffix = f"{prog_name}-{args.tag}-{timestamp}"
    if args.analyze == "counters":
        analyze_threads_vs_counters(threads, results, name_suffix)
    elif args.analyze == "hotspots":
        analyze_threads_vs_hotspots(threads, results, name_suffix)
