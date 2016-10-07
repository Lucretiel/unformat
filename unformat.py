from string import Formatter
import itertools
import sys
import re
from collections import namedtuple

if sys.version_info.major == 2:
	from itertools import izip as zip, imap as map


def pairwise(iterable):
	"s -> (s0,s1), (s1,s2), (s2, s3), ..."
	a, b = itertools.tee(iterable)
	next(b, None)
	return zip(a, b)


class UnformatError(Exception):
	pass


class InvalidIdentifierError(UnformatError):
	def __init__(self, identifier):
		UnformatError.__init__(
			self,
			"Invalid identifier in format string: {}".format(identifier),
			identifier
		)


class InvalidFormatSpecError(UnformatError):
	def __init__(self, spec):
		UnformatError.__init__(
			self,
			"Invalid format spec in format string: {}".format(spec),
			identifier)


class AmbiguousPatternError(UnformatError):
	# TODO: capture the exact position of the error
	pass


class AdjacentWhitespaceError(AmbiguousPatternError):
	# TODO: error message here
	pass


class AdjacentPatternError(AmbiguousPatternError):
	pass


class DuplicateFieldName(UnformatError):
	pass


class FormatSpec(namedtuple('FormatSpec',
	'fill, align, sign, alternate, width, comma, precision, type'
)):
	__slots__ = ()

	@classmethod
	def parse(cls, format_spec):
		match = re.match(
			r'''
				^(?:(?P<fill>.)?(?P<align>[<>=^]))?
				(?P<sign>[-+ ])?
				(?P<alternate>\#)?
				(?P<zero>0)?
				(?P<width>[1-9][0-9]*)?
				(?P<comma>,)?
				(?:\.(?P<precision>[0-9]+))?
				(?P<type>[bcdeEfFgGnosxX%])?$
			''',
			format_spec,
			re.VERBOSE
		)
		if not match:
			raise InvalidFormatSpec(format_spec)

		fields = match.groupdict()

		for bool_field in 'alternate', 'comma', 'zero':
			fields[bool_field] = fields[bool_field] is not None

		for int_field in 'width', 'precision':
			if fields[int_field] is not None:
				fields[int_field] = int(fields[int_field])

		if fields['zero']:
			fields.setdefault('fill', '0')
			fields.setdefault('align', '=')
			del fields['zero']

		# TODO: validate that there are no invalid combinations
		# TODO: set all the other DEFAULT_DATE_IDS

		return cls(**fields)


def _gen_regex_string(pattern_format):
	with
