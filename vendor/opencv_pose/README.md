# OpenCV Zoo person detection and pose estimation

`mp_persondet.py`, `mp_pose.py` and `LICENSE` are copied without modification from
[OpenCV Zoo](https://github.com/opencv/opencv_zoo) at commit
`47534e27c9851bb1128ccc0102f1145e27f23f98`:

- `models/person_detection_mediapipe/mp_persondet.py`
- `models/pose_estimation_mediapipe/mp_pose.py`
- `models/pose_estimation_mediapipe/LICENSE`

License: Apache-2.0. Model weights are downloaded separately to
`.runtime/models/image_filter/` and verified against their Git LFS SHA-256 hashes
by `spider/image_filter.py`. The person model is 11,990,159 bytes and the pose
model is 5,557,238 bytes. No downloaded images are uploaded to a service.
