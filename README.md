# Make Forward Solution

[![Run on Brainlife.io](https://img.shields.io/badge/Brainlife-bl.app.904-blue.svg)](https://doi.org/10.25663/brainlife.app.904)

## Description

Computes an MEG/EEG forward solution (lead-field matrix) using MNE-Python's
`mne.make_forward_solution`. The forward solution maps from source space (dipoles on the
cortical surface) to sensor space (MEG/EEG channels). It combines a pre-computed source space
(`src.fif`), a coregistration transform (`trans.fif`), and a BEM solution (`bem-sol.fif`). If no
source space is provided, the app falls back to an fsaverage `oct6` template source space; if no
trans/BEM is provided and the data is EEG-only, it falls back to the fsaverage 3-layer template
BEM (a sphere model is not used because radial dipoles give zero potential on a perfect sphere).

The app generates:
- the forward solution (`fwd.fif`)
- an HTML report
- a sensor-head alignment figure, when the fsaverage template source space is used

## Inputs

- **`mne`** (`neuro/meeg/mne/raw`): continuous data, used for channel info and projectors (one of `mne`/`epo`/`evoked` required)
- **`epo`** (`neuro/meeg/mne/epochs`): epoched data, used for channel info and projectors (one of `mne`/`epo`/`evoked` required)
- **`evoked`** (`neuro/meeg/mne/evoked`): evoked/averaged data, used for channel info and projectors (one of `mne`/`epo`/`evoked` required)
- **`output`** (`raw`, tagged `source_space`): pre-computed source space directory from app-source-space-v2 (optional; falls back to an fsaverage `oct6` template source space if absent)
- **`trans`** (`neuro/meeg/mne/trans`): coregistration transform from app-coreg-v2 (optional for EEG-only data, required for MEG)
- **`fif`** (`neuro/meg/fif`): BEM solution from app-bem-v2 (optional for EEG-only data, required for MEG)

If multiple of `mne`/`epo`/`evoked` are provided, the most downstream/processed one is used, in
the order evoked > epochs > raw.

## Outputs

- `out_dir/fwd.fif` (`neuro/meeg/mne/forward-inverse`): the forward solution (lead-field matrix)
- `out_report/report.html`: HTML report
- `out_figs/alignment.png`: sensor-head alignment figure (only when the fsaverage template source space is used)

## Configuration Parameters

| key | type | default | description |
|---|---|---|---|
| `mindist` | number | `5.0` | Minimum distance (mm) of sources from the inner skull surface; sources closer than this are removed. |

## Usage

### Running on Brainlife.io

1. Select your sensor data (`mne`, `epo`, or `evoked`) as input.
2. Optionally select a source space (`output`, from app-source-space-v2), a coregistration transform (`trans`, from app-coreg-v2), and a BEM solution (`fif`, from app-bem-v2).
3. Set `mindist` if the default is not appropriate.
4. Submit the process.
5. Review the alignment figure (if present) and the HTML report in the output viewer.

### Local Testing

```bash
# Edit config.json to point "mne"/"epo"/"evoked", "output", "trans" and "fif" at real files, then:
python main.py
```

## Pipeline Position

```
app-source-space-v2  →  src.fif   ─┐
app-coreg-v2         →  trans.fif  ├→  app-forward-v2  →  fwd.fif
app-bem-v2           →  bem.fif   ─┘
epochs / evoked / raw ─────────────┘
```

## Authors

- Guiomar Niso (https://github.com/guiomar)
- Antonio Caulín (https://github.com/AntonioCauAt)
- Maximilien Chaumon (https://github.com/dnacombo)
- obVdo (https://github.com/obVdo)

## Citations

- Hayashi, S., Caron, B.A., Heinsfeld, A.S. et al. brainlife.io: a decentralized and open-source cloud platform to support neuroscience research. Nat Methods 21, 809–813 (2024). https://doi.org/10.1038/s41592-024-02237-2
- Gramfort, A. et al. MEG and EEG data analysis with MNE-Python. Front. Neurosci. 7, 267 (2013). https://doi.org/10.3389/fnins.2013.00267

## Funding Acknowledgement

brainlife.io is publicly funded and for the sustainability of the project it is helpful to acknowledge the use of the platform. We kindly ask that you acknowledge the funding below in your code and publications.

[![NSF-BCS-1734853](https://img.shields.io/badge/NSF_BCS-1734853-blue.svg)](https://nsf.gov/awardsearch/showAward?AWD_ID=1734853)
[![NSF-BCS-1636893](https://img.shields.io/badge/NSF_BCS-1636893-blue.svg)](https://nsf.gov/awardsearch/showAward?AWD_ID=1636893)
[![NSF-ACI-1916518](https://img.shields.io/badge/NSF_ACI-1916518-blue.svg)](https://nsf.gov/awardsearch/showAward?AWD_ID=1916518)
[![NSF-IIS-1912270](https://img.shields.io/badge/NSF_IIS-1912270-blue.svg)](https://nsf.gov/awardsearch/showAward?AWD_ID=1912270)
[![NIH-NIBIB-R01EB029272](https://img.shields.io/badge/NIH_NIBIB-R01EB029272-green.svg)](https://grantome.com/grant/NIH/R01-EB029272-01)
[![NIH-NIBIB-R01EB030896](https://img.shields.io/badge/NIH_NIBIB-R01EB030896-green.svg)](https://grantome.com/grant/NIH/R01-EB030896-01)

## License

Copyright (c) 2026 MEEG Brainlife team. Licensed under AGPL-3.0, see [license.txt](license.txt).
