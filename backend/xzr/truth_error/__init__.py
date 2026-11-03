"""TRUTH-ERROR OPERATIONAL DYNAMICS: a synthetic research model of how a measurement, a classification, a warrant, a score and an institution's decision relate, and of what a wrong or unwarranted
judgement does once an institution adopts it.

Scope and limits, stated first:

* Everything here is SYNTHETIC: virtual subjects, virtual institutions, generated head poses. No real person, face video, credit, employment, housing or any other eligibility is assessed, and the module
  must not be used for that. A head pose (yaw, pitch, roll) is treated as a measurement with an error and nothing else: it is NOT an indicator of truthfulness, sincerity, character, ability to repay or
  creditworthiness, and the only classifier built on it here (``pose_rule``) is invalid BY CONSTRUCTION, to study what an institution does with an unwarranted meaning.
* The model does not say how real institutions behave. Its constants are this implementation's declared assumptions, chosen so that the mechanisms are visible; what a mechanism does under them is
  measured, and a result holds for these assumptions only.
* It extends the existing synthetic-institution line (``xzr.teoo.legal_v1``: a seeded population, a score, a threshold, appeals, a downstream institution) with the stages that line does not have as separate
  records: a sensor with an error model, a classifier with a declared verification label, a warrant, an acceptance rule, a correction at a chosen time, and a distinction between the score recovering and
  the opportunities lost. The older engine is a population aggregate and is left untouched.
"""
