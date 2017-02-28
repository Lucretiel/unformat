from string import Formatter
import itertools
import sys
import re
from collections import namedtuple

if sys.version_info.major == 2:
	from itertools import izip as zip, imap as map


def neighborwise(iterable, caps=None):
	'''
	Yield tuples of (previous, current, next). At the beginning of the
	sequence, yield None for previous, and at the end, yield None for next.
	'''
	previous_it, current_it, next_it = itertools.tee(iterable, 3)
	previous_it = itertools.chain([caps], previous_it)
	next(next_it)
	next_it = itertools.chain(next_it, [caps])
	return zip(previous_it, current_it, next_it)


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


class FormatToken:
	pass

class FormatLiteral(str, FormatToken):
	pass

class FormatPattern(
	namedtuple('FormatPattern', 'field_name, format_spec, conversion'),
	FormatToken
):
	_valid_field_name = re.compile(r'^([_a-zA-Z][_a-zA-Z0-9]*)?$')

	def __new__(cls, field_name, format_spec, conversion):
		if not cls._valid_field_name.match(field_name):
			raise InvalidIdentifierError(field_name)
		return super(FormatPattern, cls).__new__(cls, field_name, format_spec, conversion)


def is_pattern(token):
	return isinstance(token, FormatPattern)


def is_literal(token):
	return isinstance(token, FormatLiteral)


def parse_format_string(format_string):
	'''
	Convert a format string into a sequence for FormatLiterals and
	FormatPatterns
	'''
	parsed_pattern = Formatter().parse(format_string)
	for literal, field_name, format_spec, conversion in parsed_pattern:
		if literal:
			yield FormatLiteral(literal)
		if field_name is not None:
			yield FormatPattern(field_name, format_spec, conversion)


"[{ts:{date:{day:d}/{month:d}/{year:d}} {time:{hour:d}:{minute:d}:{second:d}}} {level} {module}] - {message}"
DEFAULT_DATE_IDS = frozenset([
	'date', 'time', 'datetime', 'timestamp', 'datestamp', 'ts', 'ds'
])
def gen_regex_parts(
	format_string,
	named_groups=True,
	strptime_format=None,
	date_identifiers=DEFAULT_DATE_IDS
):
	tokens = parse_format_string(format_string)
	used_identifiers = set()

	if named_groups:
		def add_group(pattern, name):
			return r'(?P<{}>{})'.format(name, pattern)
	else:
		def add_group(pattern, name):
			return r'({})'.format(pattern)

	for prev_token, token, next_token in neighborwise(tokens):
		if is_literal(token):
			yield re.escape(token)
		elif is_pattern(token):
			if token.field_name in used_identifiers:
				raise DuplicateFieldName(token.field_name)
			used_identifiers.add(token.field_name)

			if is_pattern(next_token):
				raise AdjacentPatternError()

			elif is_literal(next_token):
				next_char = next_token[0]
				# I'm fairly certain that there are *no* characters that need
				# to be escaped in a negated character class, not even ], ^, or
				# -
				yield add_group(r'[^{}]*'.format(next_char), token.field_name)
			elif next_token is None:
				yield add_group('.*', token.field_name)


def regex_from_format(format_string):
	return ''.join(gen_regex_parts(format_string))
