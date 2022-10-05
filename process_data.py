# v2.1

# this program will process data captured using the vdi_characterization program

from multiprocessing import Pool
from multiprocessing.pool import ThreadPool
import os
import re
from time import perf_counter as time

import pandas

from fileio import File_IO
from waveform_analysis import WaveformProcessor


# this is where waveform files are located
waveform_dir = r""
# this is where the matlab source files are located
original_waveform_dir = r""

output_file = os.path.join(waveform_dir, "results.csv")

fileio = File_IO(waveform_dir)

# regex strings
ifregex = re.compile(r"IF estimate: ([0-9.]+)")
matregex = re.compile(r"Original waveform filename: (.*\.mat)")

def main():
    # loop through each test series in the root directory
    for root, d_names, f_names in os.walk(waveform_dir):
        # Results for the entire test series
        print(f"Will write results to {output_file}")

        # collect any already processed data
        if os.path.exists(output_file):
            DATA = pandas.read_csv(output_file, header=None, index_col=0).squeeze("columns").to_dict()
        else:
            DATA = {}
        print(DATA)
        # list of all tests in the series
        dir_paths = [os.path.join(root, dir) for dir in d_names if os.listdir(os.path.join(root, dir))]

        for dir in dir_paths:
            testname = dir.replace("_waveforms", "")
            if testname in DATA:
                print(f"Data for test '{testname}' already exists. skipping")
                dir_paths.remove(dir)

        start = time()
        with ThreadPool(processes=1) as pool:
            results = pool.imap_unordered(process_dir_of_waveforms, dir_paths)

            for key, data in results:
                if key is None:
                    continue
                elif isinstance(key, Exception):
                    print(f"\n!!!!!!!!!!!!!Error!!!!!!!!!!!!!\n{key}\n")
                else:
                    print(f"\nDATA for {key}: {data}\n")
                    DATA[key] = data
                    pandas.DataFrame.from_dict(data=DATA, orient='index').to_csv(output_file, header=False)


        end = time()
        print(f"processing test data took: {end - start:.2f} seconds")


def process_dir_of_waveforms(dirpath):    
    root, dir = os.path.split(dirpath)

    # multithreaded printed will do strange things
    print(dir)

    # get if_estimate and original waveform file from .info file
    info_fn = dir.replace("_waveforms", ".info")
    info_fp = os.path.join(root, info_fn)
    print(f"name: {info_fn}. path: {info_fp}")
    if os.path.exists(info_fp):
        with open (info_fp, 'rt') as info_file:
            contents = info_file.read()
        if_estimate = float(ifregex.search(contents).group(1))
        owf_file = matregex.search(contents).group(1)
    else:
        #TODO: remove
        return None, None
        print(f"Could not find .info file for test dir {dir}. provide if_estimate manually:")
        inp = input("if_estimate: ")
        if_estimate = float(inp)

    owf_fp = os.path.join(original_waveform_dir, owf_file) if original_waveform_dir else owf_file

    print(f"IF estimate: {if_estimate}")
    print(f"Original waveform .mat filepath: {owf_fp}")

    try:
        proc = WaveformProcessor(if_estimate, debug=False, org_waveform=owf_fp)
    except FileNotFoundError as e:
        return e, None


    # process waveforms in directory
    SNRsum = 0
    bersum = 0
    symerrsum = 0
    bitsum = 0
    symsum = 0
    seg_count = 0
    for file in os.listdir(dirpath):
        root, dir = os.path.split(dirpath)
        longfn = os.path.join(dir, file)
        filepath = os.path.join(dirpath, file)
        samp_rate, samp_count, samples = fileio.load_waveform(filepath)

        start = time()
        SNR, nbits, biterr, nsyms, symerr = proc.process_qam(samp_rate, samples)
        end = time()

        print(f"File '{longfn}' computed in {end - start} seconds")
        SNRsum += SNR
        bersum += biterr
        symerrsum += symerr
        bitsum += nbits
        symsum += nsyms
        seg_count += 1
   
    SNRavg = SNRsum / seg_count
    berav = bersum / seg_count
    symerravg = symerrsum / seg_count


    key = dir.replace("_waveforms", "")
    return key, (SNRavg, bitsum, berav, symsum, symerravg)


if __name__ == "__main__":
    main()
    input()
