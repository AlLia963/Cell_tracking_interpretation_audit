"""Channel/time selection using distinguishable algebraic TIFF fixtures.

These arrays are software fixtures, not generated microscopy or study samples.
Install paper/figures/requirements.txt to run the four optional image IO checks.
"""
from pathlib import Path
import importlib.util,sys,tempfile,unittest
import numpy as np

AVAILABLE=all(importlib.util.find_spec(x) is not None for x in ['tifffile','PIL'])
if AVAILABLE:
    import tifffile
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'paper/figures'))
    from export_case import tiff_time_channels

@unittest.skipUnless(AVAILABLE,'Install paper/figures/requirements.txt for image IO checks')
class ImageAxes(unittest.TestCase):
    def check_channels(self,channels):
        # Each frame/channel has a distinct offset, preventing silent mixing.
        shape=(4,3,5) if channels==1 else (4,channels,3,5)
        raw=np.arange(np.prod(shape),dtype=np.uint16).reshape(shape)
        axes='TYX' if channels==1 else 'TCYX'
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'algebraic.tif'
            tifffile.imwrite(p,raw,metadata={'axes':axes},photometric='minisblack')
            actual,metadata=tiff_time_channels(p,[1,2])
        expected=np.stack([raw[1],raw[2]])
        if channels==1:expected=expected[:,None]
        np.testing.assert_array_equal(actual,expected)
        self.assertEqual(metadata['channels_per_frame'],channels)
        self.assertEqual(metadata['selected_frames'],[1,2])
    def test_single_channel_time_stack(self):self.check_channels(1)
    def test_two_channel_time_stack(self):self.check_channels(2)
    def test_three_channel_time_stack(self):self.check_channels(3)
    def test_static_and_out_of_range_frames_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'array.tif'
            tifffile.imwrite(p,np.zeros((2,3,5),np.uint8),metadata={'axes':'CYX'},photometric='minisblack')
            with self.assertRaisesRegex(ValueError,'Unsupported temporal'):tiff_time_channels(p,[0,1])
            tifffile.imwrite(p,np.zeros((2,3,5),np.uint8),metadata={'axes':'TYX'},photometric='minisblack')
            with self.assertRaisesRegex(ValueError,'outside TIFF'):tiff_time_channels(p,[0,2])

if __name__=='__main__':unittest.main()
