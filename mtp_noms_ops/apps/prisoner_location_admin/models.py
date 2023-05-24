import typing


class PrisonerLocation(typing.TypedDict):
    prisoner_number: str
    prisoner_name: str
    prisoner_dob: str
    prison: str
