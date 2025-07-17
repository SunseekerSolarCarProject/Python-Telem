from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = collect_all('tufup')
hiddenimports.extend([
    'tufup.client',
    'tufup.utils'
])