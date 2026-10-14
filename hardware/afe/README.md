**Analog Front-End for sEMG Signal Acquisition**

**Overview**

This project presents the design and implementation of a custom analog front-end (AFE) for surface electromyography (sEMG) signal acquisition. The system is intended for low-amplitude bio-signal conditioning, enabling reliable downstream processing for machine learning and embedded control applications.

The AFE is part of a larger system focused on laryngeal sEMG-based human–machine interfaces, including assistive technologies such as hands-free wheelchair control.

---

**System Architecture**

The signal acquisition chain is designed as a multi-stage analog pipeline:

Electrodes → Instrumentation Amplifier → Bandpass Filtering → Notch Filtering → Output

Key stages:

- Differential signal acquisition using a discrete instrumentation amplifier
- High-pass filtering (~20 Hz) to remove motion artifacts and DC offsets
- Low-pass filtering (~300 Hz) to limit high-frequency noise
- 50 Hz notch filter for power-line interference suppression

---

**Design Highlights**

- Designed for microvolt-level sEMG signals
- High overall gain (~70–100 dB target range)
- Multi-stage active filtering for signal conditioning
- Dual supply operation (±12 V)
- Compatible with DAQ systems and microcontroller ADCs

---

**Implementation**

The circuit was first validated on a breadboard and later realized as a custom PCB.

**Components used:**

- LM324 (Instrumentation Amplifier stage)
- UA741 (Filter stages)
- Passive RC networks for filtering
- Dedicated connectors for electrode input and output interfacing

PCB design considerations included compact layout, multi-stage routing, and separation of functional blocks such as amplification and filtering.

---

**Performance**

- Successfully amplified low-amplitude differential signals during controlled testing
- Achieved stable gain (~70 dB observed in hardware testing)
- Filter stages verified through simulation and hardware validation
- Designed to produce ML-ready sEMG signals for feature extraction pipelines

---
**Limitations**

- Performance varies significantly between controlled test inputs and real biological signals
- Sensitive to electrode placement, skin impedance, and noise coupling
- Discrete instrumentation amplifier implementation introduces limitations in CMRR and offset handling
- PCB layout and input-stage design critically affect real-world signal acquisition

---

**Applications**

- sEMG-based human–machine interfaces
- Assistive control systems
- Embedded bio-signal processing pipelines
- Research and prototyping in biomedical instrumentation

---

**Disclaimer**

This project is intended strictly for educational, research, and prototyping purposes.

The system is not certified for medical use and must not be used for diagnosis, treatment, or any clinical applications. Improper use of bio-signal acquisition hardware may pose electrical safety risks.

Users are responsible for ensuring proper isolation, grounding, and safe operating conditions when interfacing with the human body. The author assumes no liability for any damage, injury, or misuse resulting from the use of this design.

Use at your own discretion and risk.
