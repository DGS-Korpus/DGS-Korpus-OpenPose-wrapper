# DGS-Korpus OpenPose wrapper

Collect [OpenPose](https://github.com/CMU-Perceptual-Computing-Lab/openpose) frame files using the _DGS-Korpus OpenPose wrapper format_ used by the [Public DGS Corpus](http://ling.meine-dgs.de).

## The Wrapper Format
By default, OpenPose creates individual files for each frame of a video.
In contrast, the DGS-Korpus wrapper format collects the frames for all camera perspectives of a recording session in a single file.
This approach offers the following advantages over this:
1. Avoids file system slowdowns caused by having to handle many small files in the same directory.
2. Contains additional information about the recording, such as its resolution
3. Collects related recordings, such as different camera perspectives of the same event.

For more information on the _DGS-Korpus OpenPose wrapper format_, see the project note [OpenPose in the Public DGS Corpus](https://www.sign-lang.uni-hamburg.de/dgs-korpus/arbeitspapiere/AP06-2019-01.html)



## File naming patterns
Apart from the content of the OpenPose frame files, the DGS-Korpus wrapper requires several bits of information:
- **Session ID:** The identifier of the recording session, which is shared by all camera perspectives that show the same event. Each wrapper file represents one session.
- **Camera:** The identifier of the camera perspective. Each camera represents a single video recording. A wrapper file may collect multiple camera perspectives.
- **Width** and **Height:** The pixel dimensions of the input video.
- **Frame:** The frame of the input video that the frame file represents.

To provide these bits of information, they should be encoded in the file name of the input files. A regular expression with named groups is then used to extract them. The script provides several pattern presets to use, but users can also provide their own regular expression.

### Preset: `filename` _(default)_
Pattern: `ID_CAMERA_HEIGHTxWIDTH_FRAME_openpose.json`

The OpenPose command line script creates files following the pattern `VIDEONAME_FRAME_openpose.json`, so to use this preset, just name your video file according to the pattern `ID_CAMERA_HEIGHTxWIDTH` before processing it with OpenPose.


### Preset: `dirname`
Pattern: `ID_CAMERA_HEIGHTxWIDTH/VIDEONAME_FRAME_openpose.json`

Store each recording (i.e. each camera perspective) in a separate directory and provide all information (except the frame index) in the directory name. This preset ignores the name of the input video.

### Preset: `extracted`
Pattern: `ID_CAMERA.HEIGHTxWIDTH.frame_FRAME.openpose.json`

The pattern used by the [Public Corpus OpenPose frame extractor](https://github.com/DGS-Korpus/Public-Corpus-OpenPose-frame-extractor) script.
If you extracted data and now want to re-wrap it again, use this preset.

### Custom Regular Expression
To specify your own naming pattern, you can provide a custom regular expression. This regex should provide the named groups `id`, `camera`, `width`, `height` and `frame` and be able to handle the full filename path provided during script call.

**Example:** The `filename` preset uses the following regex:
```regex
^(?:.+/)*(?P<id>.+)_(?P<camera>.+)_(?P<width>\d+)x(?P<height>\d+)_(?P<frame>\d+)_keypoints\.json$

```

## Requirements
Python 2.7 or Python 3.

## Usage
```sh
wrap_openpose.py [-p PATTERN] INPUT_FILE [INPUT_FILE ...]
```

__Positional arguments:__
* `INPUT_FILE`: One of the OpenPose frame files to be collected in wrapper files. To run on a batch of similarly named files, use `*` (e.g. `dgskorpus/*.openpose.json`)

__Optional arguments:__
* `-o OUTPUT_DIR`: Directory in which to store the output file(s). Defaults to the working directory.
* `-p PATTERN`: The file name pattern preset to use. Defaults to `filename`.
* `-r REGEX`: A custom regular expression to use as file name pattern instead of one of the presets.
* `-v`: Provide information on the extraction process.
