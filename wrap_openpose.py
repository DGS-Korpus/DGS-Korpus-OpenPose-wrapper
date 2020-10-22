"""
Combine OpenPose one-frame-per-file outputs into a single JSON file using the Public DGS Corpus wrapper format.

The Public DGS Corpus (ling.meine-dgs.de) provides OpenPose data for all of its transcripts.
Each transcript collects the pose information of all its recordings in a single JSON file.
This data format is a wrapper around the one-frame-per-file format used by the OpenPose command line script.
In addition to the frame-specific information it also provides information on each recording,
such as the transcript ID, camera, and resolution used for the OpenPose output.
This script takes a set of one-frame-per-file input files and applies the wrapper to them.
"""
from __future__ import print_function
import argparse
import os
import re
import json
from collections import OrderedDict
from glob import glob
from warnings import warn


KEYPOINTS_KEY_VALUE_RE = r'("[\w_]+?_keypoints_\dd": \[)([\n\d., -e]+?)(])'

FILENAME_TEMPL = r'^(?:.+/)*(?P<id>.+)_(?P<camera>.+){}(?P<width>\d+)x(?P<height>\d+){}(?P<frame>\d+){}keypoints\.json$'
FILENAME_EXTRACTOR_RE = FILENAME_TEMPL.format(r'\.', r'\.frame_', r'\.')
FILENAME_OPFILE_RE = FILENAME_TEMPL.format('_', '_', '_')
FILENAME_OPDIR_RE = FILENAME_TEMPL.format('_', '/.*_', '_')


# Auxiliary functions
def ensure_dir(filename):
    """
    Make sure the directory actually exists.
    """
    filepath = os.path.dirname(filename)
    if filepath:
        try:
            os.makedirs(filepath)
        except os.error:
            pass


def deindent_key_value(match):
    """
    To be called by the regular expression substitution that de-indents OpenPose keypoint lists.
    Given a fully indented json file, the substitution command should be:
    json_output, subs = KEYPOINTS_KEY_VALUE_RE.sub(_deindent_key_value, json_indented)
    """
    key_string = match.group(1)
    array_content_string = match.group(2)
    array_close_string = match.group(3)
    deindented_content_items = [item.strip() for item in array_content_string.split('\n')]
    deindented_content_string = ' '.join(deindented_content_items).strip()
    return '{}{}{}'.format(key_string, deindented_content_string, array_close_string)


# Core functions
def extract_regex_group_fields(regex_match):
    """
    Extract the values from the named groups "id", "camera" "width", "height" and "frame".
    Allows for missing groups. If any of the groups were not matched, their value returns as None.
    """
    try:
        session_id = regex_match.group('id')
    except IndexError:
        session_id = None

    try:
        camera = regex_match.group('camera')
    except IndexError:
        camera = None

    try:
        width = int(regex_match.group('width'))
    except IndexError:
        width = None

    try:
        height = int(regex_match.group('height'))
    except IndexError:
        height = None

    try:
        frame = int(regex_match.group('frame'))
    except IndexError:
        frame = None

    return session_id, camera, width, height, frame


def group_files(filenames,
                filename_re=FILENAME_OPFILE_RE,
                verbose=False):
    """
    Group all filenames by their session ID, camera (aka recording), resolution (i.e. width x height) and frame index.
    :param filenames: List of filenames to be grouped together.
    :param filename_re: Regex string with named groups used to extract metadata (see extract_regex_group_fields()).
    :param verbose: If true, print script progress information.
    :return: Dict mapping session ID -> camera -> (width, height) -> [frame, filename]
    """
    id2cam2res2frame_file_tuples = {}
    frame_file_lists = []  # A flat representation of the (frame, file)-tuple lists; used in the later sorting step.
    for filename in filenames:
        if os.path.isfile(filename):
            filename_match = re.search(filename_re, filename)
            if filename_match:
                session_id, camera, width, height, frame = extract_regex_group_fields(filename_match)
                resolution = (width, height)

                cam2res2frame_file_tuples = id2cam2res2frame_file_tuples.setdefault(session_id, {})
                res2frame_file_tuples = cam2res2frame_file_tuples.setdefault(camera, {})
                if resolution not in res2frame_file_tuples:
                    frame_file_tuples = []
                    res2frame_file_tuples[resolution] = frame_file_tuples
                    frame_file_lists.append(frame_file_tuples)
                else:
                    frame_file_tuples = res2frame_file_tuples[resolution]

                if frame in frame_file_tuples:
                    raise ValueError('Multiple files match the same recording frame: "{}" vs "{}"'.format(
                        filename, frame_file_tuples[frame]))
                else:
                    frame_file_tuples.append((frame, filename))

            elif verbose:
                print("Ignored file not matching filename pattern: {}".format(filename))

    # Sort lists by frame index
    for frame_file_tuples in frame_file_lists:
        frame_file_tuples.sort()

    return id2cam2res2frame_file_tuples


def sanity_check_groups(id2cam2res2frame_file_tuples):
    """
    Print warning if there is a recording (camera of a session) with multiple possible resolutions.
    :param id2cam2res2frame_file_tuples: A session dict as it is returned by group_files()
    """
    for session_id, cam2res2frame_file_tuples in id2cam2res2frame_file_tuples.items():
        for camera, res2frame_file_tuples in cam2res2frame_file_tuples.items():
            if len(res2frame_file_tuples) > 1:
                resolutions = ['{}x{}'.format(h, w) for h, w in res2frame_file_tuples]
                warn('Encountered multiple resolutions for recording "{}" of session "{}": {}'.format(
                    camera, session_id, ', '.join(resolutions)))


def load_recording(frame_file_tuples, session_id=None, camera=None, width=None, height=None, verbose=False):
    """
    Load all frames of a single recording and return the dict representation of the recording.
    :param frame_file_tuples: List of (frame index, filename) tuples. Files are loaded in frame order.
    :param session_id: The identifier of this multi-camera recording session.
    :param camera: The identifier of this specific recording (i.e. camera angle) within the session.
    :param width: An integer representing the pixel width of the video file with which the OpenPose data was computed.
    :param height: An integer representing the pixel height of the video file with which the OpenPose data was computed.
    :param verbose: If true, print script progress information.
    :return:
    """
    if verbose:
        print('Loading {} frames for recording "{}" of session "{}"'.format(len(frame_file_tuples), camera, session_id))

    # Set up recording dictionary
    recording_dict = OrderedDict()
    if session_id is not None:
        recording_dict['id'] = str(session_id)
    if camera is not None:
        recording_dict['camera'] = str(camera)
    if width is not None:
        recording_dict['width'] = int(width)
    if height is not None:
        recording_dict['height'] = int(height)

    # Load frame data
    recording_dict['frames'] = frame2data = OrderedDict()
    for frame, filename in sorted(frame_file_tuples):
        with open(filename) as f:
            frame2data[frame] = json.load(f, object_pairs_hook=OrderedDict)

    return recording_dict


def write_wrapper(filename, recordings, verbose=False):
    """
    Write wrapped OpenPose data to file.
    Applies special indentation rules to prevent keypoint lists from being indented.

    :param filename: The filename of the output file
    :param recordings: A list of recording dicts. Each recording dict contains metadata as well as the key "frames"
                       which maps to another dict that maps frame indices to OpenPose output dict of that frame.
    :param verbose: If true, print script progress information.
    """
    if verbose:
        print('Write wrapper file: {}'.format(filename))

    ensure_dir(filename)
    fullindent_json = json.dumps(recordings, sort_keys=False, indent=2)
    slimindent_json = re.sub(KEYPOINTS_KEY_VALUE_RE, deindent_key_value, fullindent_json, flags=re.DOTALL)

    with open(filename, 'w') as w:
        w.write(slimindent_json)


def batch_wrap_json_frames(input_batches, output_dir=None, filename_re=FILENAME_OPFILE_RE, verbose=False):
    """
    Batch process a list of input file glob patterns and collect the resulting OpenPose frame files in
    DGS-Korpus OpenPose wrapper files.
    :param input_batches: A list of filenames or glob patterns.
    :param output_dir: The directory in which to store
    :param filename_re: Regex string with named groups used to extract metadata (see extract_regex_group_fields()).
    :param verbose: If true, print script progress information.
    :return:
    """
    input_files = []
    for input_batch in input_batches:
        for input_file in glob(input_batch):
            input_files.append(input_file)

    if verbose:
        print('Preparing to wrap {} OpenPose frame files.'.format(len(input_files)))

    input_files.sort()
    wrap_json_frames(input_filenames=input_files, output_dir=output_dir, filename_re=filename_re, verbose=verbose)

    if verbose:
        print('Completed extraction.')


# Main function
def wrap_json_frames(input_filenames, output_dir=None, filename_re=FILENAME_OPFILE_RE, verbose=False):
    """
    Collect OpenPose frame files in DGS-Korpus OpenPose wrapper files.

    Take single-frame outputs by OpenPose and collect them in a single file per recording session.
    Each recording session may potentially consist of several recordings, each of which is assumed to be a different
    camera's perspective of the same session.

    Each recording consists of its session ID, camera name and the video resolution (height and width in pixels) and a
    mapping of frames to OpenPose output. If OpenPose did not generate an output for a frame (because no people were
    recognised in it), the frame is also missing from the frame mapping.

    To be included in the output, filenames must match the pattern specified by `filename_re`. This pattern is also
    used to extract metadata (session ID, camera, width, height, frame) by virtue of named regex groups. These groups
    are not mandatory, but their omission will result in missing information. If session ID and camera are omitted,
    it is assumed that all input files belong to the same recording. If that is not the case, clashing frame indices
    may lead to exceptions.

    Each session is stored in its own file. The files are named following the pattern "SESSION_ID.openpose.json.
    If the given filename regex allows for missing session IDs (by omitting the `id` group or making it optional),
    the filename defaults to "session.openpose.json.

    :param input_filenames: List of all files to be wrapped.
    :param output_dir: The directory in which to store
    :param filename_re: Regex string with named groups used to extract metadata (see extract_regex_group_fields()).
    :param verbose: If true, print script progress information.
    """
    id2cam2res2frame_file_tuples = group_files(filenames=input_filenames, filename_re=filename_re,
                                               verbose=verbose)
    sanity_check_groups(id2cam2res2frame_file_tuples)

    for session_id, cam2res2frame_file_tuples in id2cam2res2frame_file_tuples.items():
        if verbose:
            print('Processing cameras for session "{}": {}'.format(session_id, ', '.join(cam2res2frame_file_tuples)))

        recordings = []
        # Load recordings of this session
        for camera in sorted(cam2res2frame_file_tuples):
            res2frame_file_tuples = cam2res2frame_file_tuples[camera]
            for (width, height), frame_file_tuples in res2frame_file_tuples.items():
                recording = load_recording(frame_file_tuples=frame_file_tuples, session_id=session_id, camera=camera,
                                           width=width, height=height, verbose=verbose)
                recordings.append(recording)

        # Determine name of output file
        if session_id is None:
            session_id = 'session'
        output_filename = '{}.openpose.json'.format(session_id)
        if output_dir is not None:
            output_filename = os.path.join(output_dir, output_filename)

        # Write wrapped data of session to file
        write_wrapper(filename=output_filename, recordings=recordings, verbose=verbose)


def main():
    key2pattern = {'filename': FILENAME_OPFILE_RE,
                   'dirname': FILENAME_OPDIR_RE,
                   'extracted': FILENAME_EXTRACTOR_RE}

    parser = argparse.ArgumentParser(usage='Collect OpenPose frame files in DGS-Korpus OpenPose wrapper files.')
    parser.add_argument('input_file_batches', nargs='+', metavar='INPUT_FILE',
                        help='The OpenPose frame files to collect in per-session wrappers. '
                             'To run on a batch of similarly named files, use * (e.g. myrecording_*_keypoints.json)')
    parser.add_argument('-o', '--output', '--outputdir', metavar='OUTPUT_DIR',
                        help='Directory in which to store the output file(s). Defaults to the working directory.')
    parser.add_argument('-p', '--preset', metavar='PRESET_NAME',
                        choices=list(key2pattern), default='filename',
                        help='Choose a preset pattern for extraction of information from filenames and directories.'
                             'Values can be `filename` (ID_CAMERA_HEIGHTxWIDTH_FRAME_openpose.json), '
                             '`dirname` (ID_CAMERA_HEIGHTxWIDTH/VIDEONAME_FRAME_openpose.json), or'
                             '`extracted` for files created by the Public Corpus frame extractor script.'
                             
                             'If a custom regex (-r) is provided, this selection is ignored.')
    parser.add_argument('-r', '--regex', '--regexp', metavar='REGEX',
                        help='Specify a custom regular expression for extracting information from filenames.'
                             'The custom regex takes priority over any specified preset.')
    parser.add_argument('-v', '--verbose', action='store_true', help='Provide information on the extraction process.')
    args = parser.parse_args()

    if args.regex:
        filename_re = args.regex
    else:
        filename_re = key2pattern[args.preset]

    batch_wrap_json_frames(input_batches=args.input_file_batches, output_dir=args.output, filename_re=filename_re,
                           verbose=args.verbose)


if __name__ == '__main__':
    main()
