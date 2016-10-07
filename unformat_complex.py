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


# Quick heirarchy reference:
#
#    FormatLiteral
#    FormatWhitespace
#    FormatPattern
#        FormatNumber
#        FormatString
#        FormatDate
#
# In general, patterns can't be adjacent to each other, and whitespace can't be
# adjacent to itself.

# TODO: __slots__ = ()?
class FormatLiteral(str):
	pass


class FormatWhitespace():
	pass


class FormatPattern(namedtuple('FormatGroup', 'field_name, format_spec, conversion')):
	_valid_field_name = re.compile(r'^([_a-zA-Z][_a-zA-Z0-9]*)?$')

	def __new__(cls, field_name, format_spec, conversion):
		if not cls._valid_field_name.match(field_name):
			raise InvalidIdentifierError(field_name)
		return super(FormatPattern, cls).__new__(cls, field_name, format_spec, conversion)


class FormatNumber(FormatPattern):
	pass


class FormatString(FormatPattern):
	pass


class FormatDate(FormatPattern):
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


def is_special_pattern(self, matching_ids, type_str):
	'''
	Helper method to detect date and whitespace patterns
	'''
	return (
		self.field_name.lower() in matching_ids or
		type_str is not None and self.conversion == type_str
	)


def _is_special_pattern(field_name, conversion, ids, type_char):
	return field_name.lower() in ids or type_char is not None and type_char == conversion


DEFAULT_DATE_IDS = frozenset([
	'date', 'time', 'datetime', 'timestamp', 'datestamp', 'ts', 'ds'
])

DEFAULT_WHITESPACE_IDS = frozenset([
	'w', 'white', 'whitespace'
])


def _get_bad_character(next_group):
	if isinstance(next_group, FormatLiteral):
		return re.escape(next_group[0])
	elif isinstance(next_group, FormatWhitespace):
		return '\s'
	elif next_group is None:
		return
	elif isinstance(next_group, FormatPattern):
		raise AdjacentPatternError()


def _gen_regex_string(
	format_string,
	include_date_group_names=True,
	fancy_groups=True,
	date_type='d',
	white_type='w',
	date_ids=DEFAULT_DATE_IDS,
	white_ids=DEFAULT_WHITESPACE_IDS,
):
	used_identifiers = set()

	def emit_patterns():
		# Convert the format string to a stream of format patterns, matching
		# them up pairwise, and end with None.
		for literal, field_name, format_spec, conversion in Formatter().parse(format_string):
			if literal:
				yield FormatLiteral(literal)
			if field_name is not None:
				if _is_special_pattern(field_name, conversion, date_ids, date_type):
					yield FormatDate(field_name, format_spec, conversion)
				elif _is_special_pattern(field_name, conversion, white_ids, white_type):
					yield FormatWhitespace()
				else:
					# TODO: numeric types
					yield FormatString(field_name, format_spec, conversion)
		yield None

	def combine_patterns():
		'''
		Combine the emitted patterns in a pairwise way, and also check for
		previous whitespace
		'''
		previous_whitespace = False
		for current_group, next_group in pairwise(emit_patterns()):
			yield previous_whitespace, current_group, next_group
			previous_whitespace = isinstance(current_group, FormatWhitespace)


	# These helpers implement the fancy_groups rules
	def basic_group(body):
		return "({})".format(body)

	if fancy_groups:
		def named_group(name, body):
			# Make sure the name is pre-validated, and the body valid.
			return basic_group(body) if body == "" else "(?P<{}>{})".format(name, body)

		def noncapture_group(body):
			return "(?:{})".format(body)

	else:
		noncapture_group = basic_group

		def named_group(name, body):
			return basic_group(body)

	def optional_group(body):
		return noncapture_group(body) + "?"


	for previous_whitespace, current_group, next_group in combine_patterns()
		if isinstance(current_group, FormatLiteral):
			yield re.escape(current_group)

		elif isinstance(current_group, FormatWhitespace):
			# This is kind of a wierd case, because ordinarily adjacent
			# patterns are simply always illegal, but in this case it's ok, as
			# long as the next pattern doesn't start with whitespace.
			if (
				isinstance(next_group, FormatLiteral) and next_group[0].isspace() or
				isinstance(next_group, FormatWhitespace)
			):
				raise AdjacentWhitespaceError()

			# For Date and Generic patterns, we leave it up to the pattern
			# itself to compile a regex that doesn't start with whitespace by
			# examining previous_whitespace.
			yield r'\s+'

		elif isinstance(current_group, FormatPattern):
			field_name, format_spec, conversion = current_group

			if field_name in used_identifiers:
				raise DuplicateFieldName(field_name)
			used_identifiers.add(field_name)

			body_pattern = named_group(field_name, "{body}")

			if isinstance(current_group, FormatDate):
				# TODO: make sure the date type doesn't start with whitespace if previous_whitespace is true.
				raise NotImplementedError("Dates are not implemented yet :(")

			elif isinstance(current_group, FormatNumber):
				raise NotImplementedError("Numbers are not implemented yet :(")

			elif isinstance(current_group, FormatString):
				if previous_whitespace:
					raise NotImplementedError("{whitespace}{pattern} not implmeneted yet")
				else:


			else:
				raise RuntimeError("Something impossible happened!")


		else:
			raise RuntimeError("Something impossible happened!")
