import pytest
import asyncio
import sys
from unittest.mock import patch, MagicMock

from app.windows.volume import WindowsVolumeService, WindowsAPIUnavailable, CoreAudioFailed

@pytest.mark.asyncio
async def test_non_windows_unavailable():
    with patch('sys.platform', 'linux'):
        service = WindowsVolumeService()
        with pytest.raises(WindowsAPIUnavailable):
            await service.get_state()

@pytest.mark.asyncio
async def test_volume_get_success():
    with patch('sys.platform', 'win32'):
        service = WindowsVolumeService()
        
        # Mocking COM and pycaw
        mock_pythoncom = MagicMock()
        mock_pycaw = MagicMock()
        
        mock_volume_interface = MagicMock()
        mock_volume_interface.GetMasterVolumeLevelScalar.return_value = 0.55 # 55%
        mock_volume_interface.GetMute.return_value = 0 # False
        
        mock_pycaw.AudioUtilities.GetSpeakers.return_value.EndpointVolume = mock_volume_interface
        
        with patch.dict('sys.modules', {
            'pythoncom': mock_pythoncom,
            'pycaw.pycaw': mock_pycaw,
            'comtypes': MagicMock()
        }):
            level, muted = await service.get_state()
            assert level == 55
            assert muted is False
            
            # Check COM was initialized and uninitialized
            mock_pythoncom.CoInitialize.assert_called_once()
            mock_pythoncom.CoUninitialize.assert_called_once()

@pytest.mark.asyncio
async def test_com_uninitialized_on_exception():
    with patch('sys.platform', 'win32'):
        service = WindowsVolumeService()
        
        mock_pythoncom = MagicMock()
        mock_pycaw = MagicMock()
        
        # Trigger an exception during COM execution
        mock_pycaw.AudioUtilities.GetSpeakers.side_effect = Exception("Boom")
        
        with patch.dict('sys.modules', {
            'pythoncom': mock_pythoncom,
            'pycaw.pycaw': mock_pycaw,
            'comtypes': MagicMock()
        }):
            with pytest.raises(CoreAudioFailed):
                await service.get_state()
            
            mock_pythoncom.CoInitialize.assert_called_once()
            # Still uninitialized!
            mock_pythoncom.CoUninitialize.assert_called_once()
