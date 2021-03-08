import os
import base64
import hashlib
import binascii

from pathlib import Path

import fire

from Bio import SeqIO
from Bio.Seq import Seq

from konstel.res import alphabets
import konstel.schema as schema 

import konstel.classes as classes
import konstel.formats as formats
import konstel.encodings as encodings
import konstel.helpers as helpers

        

def prepare(string, spec):
    ''''''
    if spec['remove_whitespace']:
        string = string.translate(str.maketrans('', '', ' \n\t\r'))
    if any(spec['strip_characters']):  # any() since schema default [''] is truthy
        string = string.strip(''.join(spec['strip_characters']))
    return string


def validate(string, spec):
    ''''''
    if spec['min_length']:
        if len(string) < spec['min_length']:
            raise RuntimeError(f'Validation failed: min_length')
    if spec['max_length']:
        if len(string) > spec['max_length']:
            raise RuntimeError(f'Validation failed: max_length')
    return True


def make_hash(string, algorithm):
    ''''''
    Hash = getattr(hashlib, algorithm)(string.encode())
    return Hash


def output(Hash, spec):
    ''''''
    encodings_raw = {n: getattr(encodings, m['type'])(Hash) for n, m in spec.items()}
    encodings_fmt = {}
    for name, encoding_raw in encodings_raw.items():
        length = spec[name]['length'] if 'length' in spec[name] else len(encoding_raw)
        prefix = spec[name]['prefix'] if 'prefix' in spec[name] else ''
        encodings_fmt[name] = f"{prefix}{encoding_raw[:length]}"
        if spec[name].get('include_full'):
            encodings_fmt[f'{name}_full'] = f"{prefix}{encoding_raw}"
    return encodings_fmt


def initial_directive(string, scheme, directive, spec):
    ''''''
    if 'prepare' in spec[scheme]['directives'][directive]:
        string = prepare(string, spec[scheme]['directives'][directive]['prepare'])
    if 'validate' in spec[scheme]['directives'][directive]:
        validate(string, spec[scheme]['directives'][directive]['validate'])
    return string


def final_directive(string, scheme, directive, spec):
    ''''''
    string = initial_directive(string, scheme, directive, spec)
    Hash = make_hash(string, spec[scheme]['algorithm'])
    outputs = output(Hash, spec[scheme]['encodings'])
    return outputs


def gen(scheme, string=None, file=None, format=None):
    ''''''
    PACKAGE_PATH = os.path.dirname(os.path.dirname(__file__))
    scheme, _, directive = scheme.partition('.')

    # Load scheme specification
    yaml_path = Path(f'{PACKAGE_PATH}/schemes/{scheme}.yaml')
    if not os.path.exists(yaml_path):
        raise FileNotFoundError(f'Failed to open specification for scheme {scheme}')
    spec = schema.load_scheme(yaml_path.read_text()).data

    # Validate presence and unambiguity of scheme, directive and format
    if scheme not in spec:
        raise RuntimeError(f'Unrecognised scheme {scheme}.')
    if not directive:
        if len(spec[scheme]['directives']) == 1:  # One option
            directive = next(iter(spec[scheme]['directives']))
        else:
            raise RuntimeError(f'Ambiguous directive for scheme {scheme}')
    if directive not in spec[scheme]['directives']:
        raise RuntimeError(f'Unrecognised directive {directive} for scheme {scheme}')
    if not format:
        if len(spec[scheme]['directives'][directive]['formats']) == 1:
            format = next(iter(spec[scheme]['directives'][directive]['formats']))
        else:
            raise RuntimeError(f'Ambiguous format for directive {directive} of scheme {scheme}')
    
    # Validate string and file arguments, read file contents into string
    if string and file:
        raise RuntimeError(f'Specify either a string or a file path')
    if not string and not file:
        raise RuntimeError(f'Unspecified string or file path')
    if file and not os.path.exists(file):
        raise FileNotFoundError(f'File {file} not found ')
    if file:
        string = Path(file).read_text()
    string = getattr(formats, format)(string)

    # Handle two chained directives
    target = spec[scheme]['directives'][directive].get('target')
    if target:
        string = initial_directive(string, scheme, target, spec)
    outputs = final_directive(string, scheme, directive, spec)
    
    return outputs


# def validate_scheme():
#     if hash_algorithm not in hash_funcs:
#         raise RuntimeError(f'Unrecognised hash function {hash_algorithm}')

# Validate target graph


def hash_b10(sequence):
    '''Returns base10 hash from string'''
    h = hashlib.sha1(sequence.encode())
    h_b10 = str(int(binascii.hexlify(h.digest()), 16))
    return h_b10

def hash_b32(sequence):
    '''Returns base32 hash from string'''
    h = hashlib.sha1(sequence.encode())
    h_b32 = base64.b32encode(h.digest()).decode().lower()
    return (h_b32)

def hash_prot_b10(sequence):
    '''Returns base10 hash of string comprising unambiguous IUPAC amino acids'''
    alphabet = set(list('ARNDCQEGHILKMFPSTWYV'))
    sequence_fmt = sequence.upper().strip('*').translate(str.maketrans('', '', ' \n\t\r'))
    assert(sequence_fmt != '' and set(sequence_fmt).issubset(alphabet))
    return hash_b10(sequence_fmt)

def hash_prot_b32(sequence):
    '''Returns base32 hash of string comprising unambiguous IUPAC amino acids'''
    alphabet = set(list('ARNDCQEGHILKMFPSTWYV'))
    sequence_fmt = sequence.upper().strip('*').translate(str.maketrans('', '', ' \n\t\r'))
    assert(sequence_fmt != '' and set(sequence_fmt).issubset(alphabet))
    return hash_b32(sequence_fmt)

def hash_nuc_b10(sequence):
    '''Returns base10 encoded hash of string comprising characters {A,C,G,T,U}'''
    alphabet = set(list('ACGTU'))
    sequence_fmt = sequence.upper().translate(str.maketrans('', '', ' \n\t\r'))
    assert(sequence_fmt != '' and set(sequence_fmt).issubset(alphabet))
    return hash_b10(sequence_fmt)

def hash_nuc_b32(sequence):
    '''Returns base32 encoded hash of string comprising characters {A,C,G,T,U}'''
    alphabet = set(list('ACGTU'))
    sequence_fmt = sequence.upper().translate(str.maketrans('', '', ' \n\t\r'))
    assert(sequence_fmt != '' and set(sequence_fmt).issubset(alphabet))
    return hash_b32(sequence_fmt)

def phoneme_from_hash_b10(h_b10):
    '''Returns phoneme from base10 hash'''
    vowel_map = dict(zip(map(str, range(10)), 'aeiou'*2))
    consonant_map = dict(zip(map(str, range(10)), 'fhklmprstv'))
    phoneme = ''
    for char_i, char in enumerate(h_b10[:8]):
        if not char_i % 2:
            phoneme += consonant_map[char]
        else:
            phoneme += vowel_map[char]
    return phoneme

def phoneme_generic(sequence):
    '''Returns 8 character phoneme from string'''
    return phoneme_from_hash_b10(hash_b10(sequence))

def phoneme_prot(sequence):
    '''Returns 8 character phoneme of string comprising unambiguous IUPAC amino acids'''
    return phoneme_from_hash_b10(hash_prot_b10(sequence))

def phoneme_nuc(sequence):
    '''Returns 8 character phoneme of string comprising characters {A,C,G,T,U}'''
    return phoneme_from_hash_b10(hash_nuc_b10(sequence))


# ---------- Main library functions ----------


def protein(sequence, hash_length=4):
    '''Returns dict of IDs given a string comprising unambiguous IUPAC amino acids'''
    h_b32 = hash_prot_b32(sequence)
    phoneme = phoneme_prot(sequence)
    return {'phoneme': phoneme,
            'hash': h_b32[:hash_length],
            'hash_full': h_b32,
            'sequence': sequence}

def nucleotide(sequence, hash_length=4):
    '''Returns dict of IDs given a string comprising characters {A,C,G,T,U}'''
    h_b32 = hash_nuc_b32(sequence)
    phoneme = phoneme_nuc(sequence)
    return {'phoneme': phoneme,
            'hash': h_b32[:hash_length],
            'hash_full': h_b32,
            'sequence': sequence}

def generic(sequence, hash_length=4):
    '''Returns dict of IDs given a string'''
    h_b32 = hash_b32(sequence)
    phoneme = phoneme_generic(sequence)
    return {'phoneme': phoneme,
            'hash': h_b32[:hash_length],
            'hash_full': h_b32,
            'sequence': sequence}


# ---------- SARS-CoV-2 functions ----------


def sars2_nuc_to_spike_prot(nuc_sequence):
    '''Returns translated SARS-CoV-2 spike contained in nucleotide string'''
    nuc_sequence_fmt = nuc_sequence.translate(str.maketrans('', '', ' \n\t\r'))
    seq = Seq(nuc_sequence_fmt)
    s_start_seq = 'atgtttgttttt'  # First 4 codons of Wuhan-Hu-1
    s_end_seq = 'ttacattacacataa'  # Last 5 codons of Wuhan-Hu-1
    s_start_pos = str(seq).lower().index(s_start_seq)
    s_end_pos = str(seq).lower().index(s_end_seq) + len(s_end_seq)
    spike_nucl = seq[s_start_pos:s_end_pos]
    spike_prot = str(spike_nucl.ungap().translate()).strip('*')
    assert(1200 < len(spike_prot) < 1300)  # SARS-CoV-2 is ~1270AAs long 
    return spike_prot

def sars2_nuc_fasta_to_spike_prot(fasta_path):
    '''Returns translated SARS-CoV-2 spike contained in nucleotide fasta'''
    record = SeqIO.read(fasta_path, 'fasta')
    spike_prot = sars2_nuc_to_spike_prot(str(record.seq))
    return spike_prot

def sars2_spike_from_nuc(nuc_sequence, hash_length=4):
    '''Returns hash of SARS-CoV-2 spike sequence contained in nucleotide string'''
    prot_sequence = sars2_nuc_to_spike_prot(nuc_sequence)
    h_b32 = hash_prot_b32(prot_sequence)
    phoneme = phoneme_prot(prot_sequence)
    return {
        'phoneme': phoneme,
        'hash': h_b32[:hash_length],
        'hash_full': h_b32,
        'sequence': prot_sequence}

def sars2_spike_from_nuc_fasta(fasta_path, hash_length=4):
    '''Returns dict of IDs of SARS-CoV-2 spike sequence contained in nucleotide fasta'''
    prot_sequence = sars2_nuc_fasta_to_spike_prot(fasta_path)
    h_b32 = hash_prot_b32(prot_sequence)
    phoneme = phoneme_prot(prot_sequence)
    return {
        'phoneme': phoneme,
        'hash': h_b32[:hash_length],
        'hash_full': h_b32,
        'sequence': prot_sequence}


def main():
    fire.core.Display = lambda lines, out: print(*lines, file=out) # Stop Fire using pager
    fire.Fire({
        'protein': protein,
        'nucleotide': nucleotide,
        'generic': generic,
        'sars2-spike-from-nuc': sars2_spike_from_nuc,
        'sars2-spike-from-nuc-fasta': sars2_spike_from_nuc_fasta,
        'gen': gen})