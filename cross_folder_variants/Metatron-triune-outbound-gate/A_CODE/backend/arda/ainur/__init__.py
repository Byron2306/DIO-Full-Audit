__all__ = [
	"AinurChoir",
	"ConstitutionalMode",
	"VerdictState",
	"ChoirVerdict",
	"AinurVerdict",
	"EvidencePacket",
	"SecretFirePacket",
	"ChoralSweep",
	"IluvatarVoiceChallenge",
]


def __getattr__(name):
	if name == "AinurChoir":
		from .choir import AinurChoir
		return AinurChoir
	if name == "ConstitutionalMode":
		from .policy import ConstitutionalMode
		return ConstitutionalMode
	if name in {
		"VerdictState",
		"ChoirVerdict",
		"AinurVerdict",
		"EvidencePacket",
		"SecretFirePacket",
		"ChoralSweep",
		"IluvatarVoiceChallenge",
	}:
		from .verdicts import (
			VerdictState,
			ChoirVerdict,
			AinurVerdict,
			EvidencePacket,
			SecretFirePacket,
			ChoralSweep,
			IluvatarVoiceChallenge,
		)
		return {
			"VerdictState": VerdictState,
			"ChoirVerdict": ChoirVerdict,
			"AinurVerdict": AinurVerdict,
			"EvidencePacket": EvidencePacket,
			"SecretFirePacket": SecretFirePacket,
			"ChoralSweep": ChoralSweep,
			"IluvatarVoiceChallenge": IluvatarVoiceChallenge,
		}[name]
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
