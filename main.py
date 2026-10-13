"""
app-forward-v2: Compute forward solution for MEG/EEG source reconstruction.

Authors : Guiomar Niso (guiomar.niso@gmail.com)
          Antonio Caulín (antoniocaulinatienzar@gmail.com) https://github.com/AntonioCauAt
          Maximilien Chaumon https://github.com/dnacombo
          obVdo https://github.com/obVdo
Based on: https://github.com/guiomar/app-fw-solution

Inputs : sensor data (epochs or raw FIF), source space (src.fif from app-source-space-v2),
         trans.fif (from app-coreg-v2), bem-sol.fif (from app-bem-v2).
Outputs: fwd.fif
"""

import os
import sys
import glob

# Headless 3D rendering — must be set BEFORE vtk/pyvista/mne.viz is imported.
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VTK_DEFAULT_RENDER_WINDOW_OFFSCREEN', '1')
os.environ.setdefault('MPLBACKEND', 'Agg')

# Resolve brainlife_utils — try local copy first, then parent monorepo
app_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(app_dir)
for search_path in [app_dir, parent_dir]:
    if os.path.isdir(os.path.join(search_path, 'brainlife_utils')):
        sys.path.insert(0, search_path)
        break

from brainlife_utils import (
    setup_matplotlib_backend,
    load_config,
    ensure_output_dirs,
    add_info_to_product,
    add_image_to_product,
    create_product_json,
    setup_offscreen_3d_backend,
)

setup_matplotlib_backend()
import matplotlib.pyplot as plt

import mne
from mne.io.constants import FIFF

mne.set_log_level('WARNING')

# == SETUP ==
ensure_output_dirs('out_dir', 'out_figs', 'out_report')
product_items = []

# == LOAD CONFIG ==
config = load_config()

# == LOAD SENSOR DATA (for channel info only — any data type works) ==
# Priority: evoked > epochs > raw (most to least downstream/processed).
# Brainlife config keys: evoked='evoked', epochs='epo', raw='mne'
# Brainlife may send a directory path — resolve to the actual FIF file.
epochs_file = config.get('epo') or None
if epochs_file and not os.path.isfile(epochs_file):
    _dir = os.path.dirname(epochs_file)
    epochs_file = None
    for name in ('meg-epo.fif', 'epochs.fif', 'epo.fif'):
        _c = os.path.join(_dir, name)
        if os.path.isfile(_c):
            epochs_file = _c
            break

raw_file = config.get('mne') or None
if raw_file and not os.path.isfile(raw_file):
    _dir = os.path.dirname(raw_file)
    raw_file = None
    for name in ('raw.fif', 'meg.fif'):
        _c = os.path.join(_dir, name)
        if os.path.isfile(_c):
            raw_file = _c
            break

evoked_file = config.get('evoked') or None
if evoked_file and not os.path.isfile(evoked_file):
    _dir = os.path.dirname(evoked_file)
    evoked_file = None
    for name in ('evokeds_ave.fif', 'ave.fif', 'evoked-ave.fif'):
        _c = os.path.join(_dir, name)
        if os.path.isfile(_c):
            evoked_file = _c
            break

info = None
try:
    if evoked_file:
        evoked = mne.read_evokeds(evoked_file)[0]
        info   = evoked.info
        add_info_to_product(product_items, f"Loaded evoked: {len(info['ch_names'])} channels", "info")
    elif epochs_file:
        data = mne.read_epochs(epochs_file, preload=False)
        info = data.info
        add_info_to_product(product_items, f"Loaded epochs: {len(data.ch_names)} channels", "info")
    elif raw_file:
        info = mne.io.read_info(raw_file)
        add_info_to_product(product_items, f"Loaded raw: {len(info['ch_names'])} channels", "info")
    else:
        add_info_to_product(
            product_items,
            "FATAL: No sensor data found. Set 'evoked', 'epochs', or 'raw' in config.json.",
            "error"
        )
        create_product_json(product_items)
        sys.exit(1)
except Exception as e:
    add_info_to_product(product_items, f"FATAL: Could not load sensor data: {e}", "error")
    create_product_json(product_items)
    sys.exit(1)

# == DETECT MODALITY ==
ch_types  = info.get_channel_types()
meg_types = {'mag', 'grad', 'ref_meg'}
eeg_count = sum(1 for t in ch_types if t == 'eeg')
meg_count = sum(1 for t in ch_types if t in meg_types)

if meg_count > 0 and eeg_count > 0:
    modality = 'meeg'
elif meg_count > 0:
    modality = 'meg'
elif eeg_count > 0:
    modality = 'eeg'
else:
    add_info_to_product(
        product_items,
        f"FATAL: No MEG or EEG channels found. Types present: {set(ch_types)}",
        "error"
    )
    create_product_json(product_items)
    sys.exit(1)

use_meg = modality in ('meg', 'meeg')
use_eeg = modality in ('eeg', 'meeg')

add_info_to_product(
    product_items,
    f"Modality: {modality} | EEG: {eeg_count} | MEG: {meg_count}",
    "info"
)

# == RESOLVE SOURCE SPACE PATH ==
# Brainlife maps raw source_space datatype to config key 'output' (a directory).
# Find the src.fif file inside that directory.
_src_dir  = config.get('output') or None
src_file  = None
_using_fsaverage_src = False
if _src_dir and os.path.isfile(_src_dir):
    # Brainlife may map the datatype straight to the .fif rather than its
    # directory; treat that as provided too, otherwise the guard below reports
    # a missing source space the user did in fact connect.
    src_file = _src_dir
elif _src_dir and os.path.isdir(_src_dir):
    for _f in os.listdir(_src_dir):
        if _f.endswith('.fif') and 'src' in _f:
            src_file = os.path.join(_src_dir, _f)
            break
    if not src_file:
        # fallback: any .fif in the directory
        _fifs = [f for f in os.listdir(_src_dir) if f.endswith('.fif')]
        if _fifs:
            src_file = os.path.join(_src_dir, _fifs[0])

# == LOAD TRANS AND BEM ==
# Brainlife config keys: trans='trans', bem='fif' (meg/fif datatype)
trans_file = config.get('trans') or None
bem_file   = config.get('fif') or None
try:
    mindist = float(config.get('mindist') or 5.0)
except (TypeError, ValueError) as e:
    add_info_to_product(
        product_items,
        f"FATAL: Invalid 'mindist' value: {config.get('mindist')!r} ({e})",
        "error"
    )
    create_product_json(product_items)
    sys.exit(1)

if mindist < 0:
    add_info_to_product(
        product_items,
        f"FATAL: 'mindist' must be >= 0 mm (got {mindist}).",
        "error"
    )
    create_product_json(product_items)
    sys.exit(1)

if trans_file:
    if os.path.isfile(trans_file):
        add_info_to_product(product_items, f"Trans file: {trans_file}", "info")
    else:
        add_info_to_product(product_items, f"Trans file not found at: {trans_file}", "warning")
        trans_file = None

if bem_file:
    if os.path.isfile(bem_file):
        add_info_to_product(product_items, f"BEM file: {bem_file}", "info")
    else:
        # meg/fif datatype names the file meg.fif — try bem-sol.fif in the same directory
        _bem_dir = os.path.dirname(bem_file)
        _alt = os.path.join(_bem_dir, 'bem-sol.fif')
        if os.path.isfile(_alt):
            bem_file = _alt
            add_info_to_product(product_items, f"BEM file (resolved): {bem_file}", "info")
        else:
            add_info_to_product(product_items, f"BEM file not found at: {bem_file} (also tried {_alt})", "warning")
            bem_file = None

# == VALIDATE INPUT COMBINATION ==
# The source space, the BEM and trans must all describe the SAME head. A source
# space is expressed in its own subject's MRI coordinates, the BEM surfaces are
# in that same subject's MRI coordinates, and trans maps head -> that MRI.
#
# MNE does not check this. make_forward_solution() will happily combine a
# template source space with a native BEM and return a forward solution that
# completes without error but places the dipoles in a different brain; the only
# symptom is sources silently discarded by the mindist containment test.
# See https://mne.tools/stable/auto_tutorials/forward/20_source_alignment.html
#
# Both native and template work, for MEG and for EEG, so long as all three
# pieces agree. The source space carries its subject name (subject_his_id),
# which is what lets a user-supplied fsaverage source space be told apart from
# a native one.
_n_headmodel = int(bool(trans_file)) + int(bool(bem_file))

# Load the source space now (if one was given) so its subject can be checked.
src = None
src_subject = None
if src_file:
    try:
        src = mne.read_source_spaces(src_file)
        src_subject = src[0].get('subject_his_id')
        add_info_to_product(
            product_items,
            f"Loaded source space: {sum(s['nuse'] for s in src)} sources"
            f" (subject: {src_subject or 'unknown'})",
            "info"
        )
    except Exception as e:
        add_info_to_product(product_items, f"FATAL: Could not load source space: {e}", "error")
        create_product_json(product_items)
        sys.exit(1)

if _n_headmodel == 1:
    _missing_hm = 'BEM' if trans_file else 'trans'
    add_info_to_product(
        product_items,
        f"FATAL: got one half of the head model but not the other — '{_missing_hm}' "
        "is missing. trans and BEM must be supplied together.",
        "error"
    )
    create_product_json(product_items)
    sys.exit(1)

if _n_headmodel == 2 and not src_file:
    add_info_to_product(
        product_items,
        "FATAL: a trans and BEM were supplied but no source space. The app would "
        "otherwise fall back to an fsaverage template source space and combine it "
        "with your native head model, placing the dipoles in a different brain. "
        "Connect the source space from app-source-space-v2 (built from the same "
        "FreeSurfer subject as the BEM), or disconnect the trans and BEM too.",
        "error"
    )
    create_product_json(product_items)
    sys.exit(1)

if _n_headmodel == 0 and src_file:
    # No head model given, so the fsaverage template BEM and trans='fsaverage'
    # will be used below. That is only consistent if the source space is itself
    # fsaverage.
    if src_subject != 'fsaverage':
        add_info_to_product(
            product_items,
            f"FATAL: the source space belongs to subject "
            f"'{src_subject or 'unknown'}', but no trans or BEM was supplied, so "
            "the fsaverage template head model would be used against it. "
            "Connect the trans (app-coreg-v2) and BEM (app-bem-v2) built from "
            f"the same subject as this source space"
            + ("" if src_subject else " (the source space carries no subject name, "
               "so consistency cannot be verified)") + ".",
            "error"
        )
        create_product_json(product_items)
        sys.exit(1)
    add_info_to_product(
        product_items,
        "Source space is fsaverage and no head model was supplied — using the "
        "fsaverage template throughout.",
        "info"
    )
    _using_fsaverage_src = True
    subjects_dir = os.path.dirname(mne.datasets.fetch_fsaverage(verbose=False))

if not src_file:
    # Nothing supplied at all — build the fsaverage template source space.
    try:
        add_info_to_product(
            product_items,
            "No source space, trans or BEM supplied — using the fsaverage "
            "template throughout (oct6).",
            "warning"
        )
        subjects_dir = os.path.dirname(mne.datasets.fetch_fsaverage(verbose=False))
        src = mne.setup_source_space(
            'fsaverage', spacing='oct6',
            subjects_dir=subjects_dir, add_dist=False, verbose=False
        )
        _using_fsaverage_src = True
        add_info_to_product(
            product_items,
            f"fsaverage source space: {sum(s['nuse'] for s in src)} sources",
            "info"
        )
    except Exception as e:
        add_info_to_product(product_items, f"FATAL: Could not create fsaverage source space: {e}", "error")
        create_product_json(product_items)
        sys.exit(1)

# == COMPUTE FORWARD SOLUTION ==
trans_obj = None
bem_sol   = None
try:
    if trans_file and bem_file:
        add_info_to_product(product_items, "Computing forward solution (trans + BEM)...", "info")
        bem_sol   = mne.read_bem_solution(bem_file)
        trans_obj = mne.read_trans(trans_file)
        fwd = mne.make_forward_solution(
            info, trans=trans_obj, src=src, bem=bem_sol,
            meg=use_meg, eeg=use_eeg,
            mindist=mindist, n_jobs=1, verbose=True
        )

    else:
        # Template path: fsaverage 3-layer BEM (ships with MNE) plus MNE's
        # built-in fsaverage head->MRI transform. Available to MEG, EEG and
        # MEEG alike.
        #
        # A sphere model must NOT be used here — radial dipoles produce zero
        # potential on a perfect sphere (Helmholtz), giving zero leadfield columns
        # → depth weighting: 1/0 = inf → NaN in make_inverse_operator.
        _bem_path = os.path.join(subjects_dir, 'fsaverage', 'bem',
                                 'fsaverage-5120-5120-5120-bem-sol.fif')
        add_info_to_product(
            product_items,
            f"No trans/BEM provided — using fsaverage 3-layer BEM: {_bem_path}",
            "info"
        )
        add_info_to_product(
            product_items,
            "Template head model: no coregistration was performed. trans='fsaverage' "
            "is a fixed transform shipped with MNE, not a fit to this subject. "
            "Source locations will be less accurate and can be off by multiple "
            "centimetres — do not over-interpret them.",
            "warning"
        )
        if use_meg:
            add_info_to_product(
                product_items,
                "MEG on the template path: MEG sensor positions come from this "
                "recording but the head is fsaverage, so a head-size mismatch is "
                "not corrected (MEG sensors are not projected onto the scalp the "
                "way EEG electrodes are). If this recording has digitized head "
                "points, coregistering against fsaverage with app-coreg-v2 and "
                "connecting trans/BEM/source space will be more accurate.",
                "warning"
            )
        fwd = mne.make_forward_solution(
            info, trans='fsaverage', src=src, bem=_bem_path,
            meg=use_meg, eeg=use_eeg,
            mindist=mindist, n_jobs=1, verbose=True
        )

    _method = "native BEM + trans" if (trans_file and bem_file) else "fsaverage 3-layer BEM (template)"
    add_info_to_product(
        product_items,
        f"Forward solution: {fwd['nsource']} sources, "
        f"{'fixed' if fwd['surf_ori'] else 'free'} orientation, {modality.upper()}, {_method}",
        "info"
    )
except Exception as e:
    # make_forward_solution(on_inside='raise', the default since MNE 1.10) raises
    # when MEG sensors fall inside the outer skin surface. On the template path
    # that means the subject's head is smaller than fsaverage, which is the
    # failure MNE-BIDS-Pipeline warns about for unscaled fsaverage.
    if 'inside the' in str(e) and 'MEG sensor' in str(e):
        add_info_to_product(
            product_items,
            f"FATAL: {e}\n\n"
            "On the fsaverage template path this means this subject's head is "
            "smaller than fsaverage, so the template scalp swallows the MEG "
            "sensors. An unscaled template cannot be used for this recording. "
            "Coregister against fsaverage with app-coreg-v2 (and build the BEM "
            "and source space from the same subject), or supply the subject's "
            "own FreeSurfer anatomy.",
            "error"
        )
    else:
        add_info_to_product(product_items, f"FATAL: Forward solution failed: {e}", "error")
    create_product_json(product_items)
    sys.exit(1)

# == SAVE OUTPUT ==
fwd_path = os.path.join('out_dir', 'fwd.fif')
try:
    mne.write_forward_solution(fwd_path, fwd, overwrite=True)
    add_info_to_product(product_items, f"Saved: {fwd_path}", "info")
except Exception as e:
    add_info_to_product(product_items, f"FATAL: Could not save forward solution: {e}", "error")
    create_product_json(product_items)
    sys.exit(1)


# == ALIGNMENT PLOT ==
# Draw the alignment that was actually used, on both valid paths.
report = mne.Report(title='Forward Solution Report')

try:
    setup_offscreen_3d_backend()

    if _using_fsaverage_src:
        _align_kwargs = dict(trans='fsaverage', subject='fsaverage',
                             subjects_dir=subjects_dir, surfaces='head')
        _align_title = 'Sensor-head alignment (fsaverage template)'
        _eeg_opts = ['original', 'projected'] if use_eeg else []
    else:
        # This app receives no FreeSurfer directory, but the head surface can
        # still be rendered: _get_head_surface() consults the BEM via
        # _bem_find_surface(bem, "head") before it ever touches subjects_dir
        # (mne/_freesurfer.py). That only works for a 3-layer BEM — a 1-layer
        # MEG BEM has no head surface, and asking for one then raises.
        _has_head_surf = any(
            s.get('id') == FIFF.FIFFV_BEM_SURF_ID_HEAD
            for s in (bem_sol.get('surfs') or [])
        )
        if _has_head_surf:
            _align_kwargs = dict(trans=trans_obj, bem=bem_sol, surfaces=['head'])
            _align_title = 'Sensor-head alignment (native BEM + trans)'
            # 'projected' requires a head surface to project onto; we have one.
            _eeg_opts = ['original', 'projected'] if use_eeg else []
        else:
            # 1-layer BEM: sensors + source points only. 'projected' must be
            # dropped or plot_alignment raises ValueError (mne/viz/_3d.py).
            _align_kwargs = dict(trans=trans_obj, bem=bem_sol, surfaces=[])
            _align_title = 'Sensor alignment (native trans, 1-layer BEM — no head surface)'
            _eeg_opts = ['original'] if use_eeg else []

    fig_align = mne.viz.plot_alignment(
        info,
        src=src,
        eeg=_eeg_opts,
        meg=['helmet', 'sensors'] if use_meg else [],
        coord_frame='mri',
        verbose=False,
        **_align_kwargs,
    )
    align_path = os.path.join('out_figs', 'alignment.png')
    fig_align.plotter.show(auto_close=False)
    fig_align.plotter.screenshot(align_path)
    try:
        fig_align.plotter.close()
    except Exception:
        pass
    add_image_to_product(product_items, _align_title, filepath=align_path)
    report.add_image(align_path, title=_align_title)

except Exception as e:
    add_info_to_product(product_items, f"Could not render alignment plot: {e}", "warning")

# == SAVE REPORT ==
report.save(os.path.join('out_report', 'report.html'), overwrite=True)

add_info_to_product(product_items, "Forward solution computed successfully.", "success")
create_product_json(product_items)
print("Done.")
