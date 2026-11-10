# Validating the rating-rubric weights against real data

## Question

The proposed rubric scored a face on five components:

| Component | Proposed weight |
|---|---|
| Harmony / averageness | 30% |
| Dimorphic features (jaw, chin, cheekbones, brow) | 25% |
| Facial adiposity (leanness) | 20% |
| Skin quality | 15% |
| Symmetry | 10% |

Do these weights match what actually predicts attractiveness ratings?

## Data and method

- **Dataset:** SCUT-FBP5500 contains 5,500 frontal faces, each rated 1–5 by 60 raters. It includes 2,000 Asian men, 750 Caucasian men, 2,000 Asian women and 750 Caucasian women. The images and labels came from a public GitHub mirror. The dataset is for non-commercial research only, so no images are stored in this repo.
- **Landmarks:** MediaPipe Face Landmarker gave 478 points per face, plus a 3-D head-pose estimate. Every face was detected.
- **Each component was measured as follows** (code in `analysis/`):
  - *Harmony:* Procrustes distance to the average face of the same sex and ethnicity
  - *Dimorphism:* position on the male↔female shape axis (LDA), scored as how typical the face is of its own sex
  - *Adiposity:* width-to-height ratio and cheek-to-jaw width ratio (Coetzee et al., 2009), scored so that higher means leaner
  - *Skin:* fine-texture roughness and colour unevenness on the cheeks and forehead
  - *Symmetry:* Procrustes mismatch between a face and its own mirror image
- All measures and ratings were standardised within each sex × ethnicity group.
- **Statistics:** each component's correlation with the rating, its multiple-regression beta, and a Shapley R² decomposition. The decomposition gives the share of the explained variance that belongs to each component; those shares are the "data weights". Finally, 10-fold cross-validated R² compares the proposed weights, equal weights and weights fitted to the data.
- **Two versions:**
  - **raw:** measures used as they are
  - **pose-controlled:** head yaw, pitch and roll, mouth opening, smile width and image sharpness regressed out of every measure first

## Main finding 1: photo pose predicts the rating more strongly than any facial measure

| Photo factor | r with rating (men) | r with rating (women) |
|---|---|---|
| Head pitch (head tilted down, looking up through the brows) | **0.52** | **0.51** |
| Head yaw (turned) | 0.27 | 0.18 |
| Mouth open / smiling | −0.06 to −0.32 | −0.10 |

In the top-rated men, the head is tilted down and they look up through the brows; these are mostly modelling shots. In the bottom-rated men, the chin is level or raised, as in ID or mugshot photos. Part of this effect is real, because the pose flatters the face. Part of it is selection, because the attractive faces in the dataset come from professional photos. That is why the two versions below bracket the true answer.

## Main finding 2: the proposed weights don't fit the data

Cross-validated R² (share of rating variance predicted on held-out faces):

| Group | Proposed weights | Equal weights | Fitted weights |
|---|---|---|---|
| Men (raw) | 0.01 | 0.02 | **0.22** |
| Men (pose-controlled) | 0.00 | 0.00 | 0.02 |
| Women (raw) | 0.05 | 0.02 | **0.31** |
| Women (pose-controlled) | 0.05 | 0.04 | 0.07 |

The proposed weights predict almost nothing for men. The main reason is that they give 70% of the weight to harmony, dimorphism and skin, and in this data those three carry little or no signal.

## Weights the data supports

The figures below are shares of explained variance (Shapley R²).

**Men (n = 2,750)**

| Component | Proposed | Data (raw) | Data (pose-controlled) | r raw / controlled |
|---|---|---|---|---|
| Adiposity (leanness) | 20% | **65%** | **82%** | +0.40 / +0.14 |
| Symmetry | 10% | 19%* | 16% | −0.28* / +0.06 |
| Harmony | 30% | 7%* | 0% | −0.21* / +0.01 |
| Skin | 15% | 7%* | 1% | −0.18* / −0.01 |
| Dimorphism | 25% | 2% | 1% | −0.09 / −0.01 |

\* These effects run in the **wrong direction** in the raw data: the "worse" score goes with a higher rating. The cause is photo artifacts. Model shots are angled (so they read as less symmetric and less average) and sharper (so they read as rougher skin). Once pose is controlled, these effects disappear.

**Women (n = 2,750)**

| Component | Proposed | Data (raw) | Data (pose-controlled) |
|---|---|---|---|
| Adiposity (leanness) | 20% | 60% | 40% |
| Dimorphism (femininity) | 25% | 30% | 48% |
| Harmony | 30% | 2% | 11% |
| Symmetry | 10% | 6% | 1% |
| Skin | 15% | 3% | 1% |

## What this means

1. **Leanness is the single strongest, most robust facial factor for men.** It wins in every version and in both ethnic groups. The cheek-to-jaw ratio alone correlates +0.38 with the rating. This is the "excess facial fat / bloat" failo from the PSL scale, and the data backs it strongly.
2. **Presentation is huge.** Head angle alone (r ≈ 0.5) beats every structural measure. The "hunter eyes" head-down pose is a large part of what makes model photos rate high, so it belongs in the rubric as its own factor.
3. **Dimorphism matters for women, not for men,** at least as measured here. This matches the literature: more masculine male faces show mixed effects.
4. **Averageness, symmetry and skin weren't supported** by these measurements. That does *not* mean they don't matter. 2-D landmark averageness and patch-based skin metrics are crude, and the controlled analysis has to work with weak signals.
5. **Simple geometry explains only a small part of the rating:** about 2–7% after pose control, and up to 22–31% raw. Deep-learning models reach r ≈ 0.9 on this dataset, so most of what raters respond to lies outside these five measures: eyes, hair, lighting, grooming and expression.

## Revised rubric (for men)

The weights below mix data and theory. Validated components are marked as such.

| Component | Weight | Status |
|---|---|---|
| Facial leanness / adiposity | 40% | Validated (strongest factor) |
| Presentation (pose, grooming, hair, photo quality) | 25% | Validated (pose r ≈ 0.5) |
| Symmetry | 10% | Weakly supported |
| Harmony / averageness | 10% | Not supported here, kept from prior literature |
| Dimorphism | 10% | Not supported for men here |
| Skin | 5% | Not supported by these measures |

## Limitations

- Most SCUT-FBP5500 raters were young Chinese adults, and the Caucasian groups are small (n = 750 each).
- The dataset contains duplicate photos of some people, for example CM638 and CM727.
- Pose and photo source are mixed together. The two versions are a lower and upper bound, not an exact answer.
- All measures are 2-D proxies. Bone structure such as maxillary projection can't be measured from a frontal photo.

## Reproducing

```bash
pip install -r analysis/requirements.txt
# images + Labels/All_labels.csv from SCUT-FBP5500; model from
# storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task
python analysis/extract_features.py <images_dir> <All_labels.csv> face_landmarker.task features.csv
python analysis/validate_weights.py features.csv analysis/results
```

Full numbers are in `analysis/results/results.json`.
