# Make Forward Solution

[![Run on Brainlife.io](https://img.shields.io/badge/Brainlife-bl.app.904-blue.svg)](https://doi.org/10.25663/brainlife.app.904)

## Description

Computes an MEG/EEG forward solution (lead-field matrix) using MNE-Python's
`mne.make_forward_solution`. The forward solution maps from source space (dipoles on the
cortical surface) to sensor space (MEG/EEG channels). It combines a pre-computed source space
(`src.fif`), a coregistration transform (`trans.fif`), and a BEM solution (`bem-sol.fif`).

These three must describe the same head. A source space is expressed in its own subject's
MRI coordinates, the BEM surfaces are in that same subject's MRI coordinates, and `trans`
maps head to that MRI — so mixing a template with native anatomy places the dipoles in a
different brain. MNE does not check this and will return a forward solution that completes
without error but is anatomically meaningless, so the app checks it instead. See
**How the app decides what to do** below.

The app generates:
- the forward solution (`fwd.fif`)
- an HTML report
- a sensor-head alignment figure, showing the transform actually used

### How the app decides what to do

`output` (source space), `trans` and `fif` (BEM) are accepted **all together or not at all**.
The source space carries the name of the subject it was built from, which is what lets a
template source space be told apart from a native one.

| `output` (src) | `trans` | `fif` (BEM) | src subject | What happens |
|---|---|---|---|---|
| ✅ | ✅ | ✅ | any | **Native.** Your anatomy throughout. Best accuracy. |
| ❌ | ❌ | ❌ | — | **Template.** fsaverage `oct6` source space, `trans='fsaverage'`, fsaverage 3-layer BEM. |
| ✅ | ❌ | ❌ | `fsaverage` | **Template**, with your own source space (lets you choose the spacing). |
| ✅ | ❌ | ❌ | native, e.g. `sub-01` | ⛔ Error — a native source space against the template head model. |
| ❌ | ✅ | ✅ | — | ⛔ Error — a template source space against your native head model. |
| ✅ | ✅ | ❌ | any | ⛔ Error — `trans` and BEM must be supplied together. |
| ✅ | ❌ | ✅ | any | ⛔ Error — `trans` and BEM must be supplied together. |

Every error names exactly which input to connect. All paths work for **MEG, EEG and MEEG**.

#### Native vs template

| | Native | Template |
|---|---|---|
| Source space | yours, from app-source-space-v2 | fsaverage `oct6` |
| Head↔MRI transform | fitted by app-coreg-v2 (ICP) | fixed `fsaverage-trans.fif`, **nothing fitted** |
| BEM | yours, from app-bem-v2 | fsaverage 3-layer |
| Needs a FreeSurfer subject? | yes | no |
| Accuracy | best available | locations can be off by **multiple centimetres** |

The template path performs **no coregistration at all**. For MEG this matters more than for
EEG: MEG sensor positions come from the recording while the head is fsaverage, and nothing
projects them onto the template scalp the way EEG electrodes are projected, so a head-size
mismatch goes uncorrected. If the subject's head is small enough that the template scalp
would swallow the MEG sensors, `make_forward_solution` raises (`on_inside='raise'`) and the
app reports it rather than producing a meaningless solution.

Where digitized head points exist, a middle route is more accurate than the template: run
app-coreg-v2, app-bem-v2 and app-source-space-v2 all against an fsaverage FreeSurfer subject,
then connect all three. That gives a real ICP fit to the subject's head points while still
needing no individual MRI.

## Inputs

- **`mne`** (`neuro/meeg/mne/raw`): continuous data, used for channel info and projectors (one of `mne`/`epo`/`evoked` required)
- **`epo`** (`neuro/meeg/mne/epochs`): epoched data, used for channel info and projectors (one of `mne`/`epo`/`evoked` required)
- **`evoked`** (`neuro/meeg/mne/evoked`): evoked/averaged data, used for channel info and projectors (one of `mne`/`epo`/`evoked` required)
- **`output`** (`raw`, tagged `source_space`): pre-computed source space from app-source-space-v2 (required unless `trans` and `fif` are also left unconnected)
- **`trans`** (`neuro/meeg/mne/trans`): coregistration transform from app-coreg-v2 (required unless `output` and `fif` are also left unconnected)
- **`fif`** (`neuro/meg/fif`): BEM solution from app-bem-v2 (required unless `output` and `trans` are also left unconnected)

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
2. Select a source space (`output`, from app-source-space-v2), a coregistration transform (`trans`, from app-coreg-v2), and a BEM solution (`fif`, from app-bem-v2) — all three, or none of them. With none connected the fsaverage template is used throughout, for MEG and EEG alike.
3. Set `mindist` if the default is not appropriate.
4. Submit the process.
5. Review the alignment figure and the HTML report in the output viewer. Check that the sensors sit on the head surface and that the source points lie inside it.

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
