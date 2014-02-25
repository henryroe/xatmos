import numpy as np
import gzip
import pandas

def _float_converter(x):
    try:
        return np.float(x)
    except ValueError:
        return np.NaN

def _int_converter(x):
    try:
        return np.int(x)
    except ValueError:
        return np.NaN


def get_hitran_molecule_number(molecule_number):
    try:
        f = gzip.open('/Users/hroe/Dropbox/refdata/hitran04/HITRAN2004/By-Molecule/Compressed-files/' +
                      ('%02i' % molecule_number) + '_hit04.par.gz', 'r')
        hitran = pandas.read_fwf(f, widths=[2, 1, 12, 10, 10, 5, 5, 10, 4, 8],
                                 header=None,
                                 names=['MoleculeNum', 'IsotopeNum', 'wavenumber', 'intensity',
                                        'WeightedTransition', 'airHWHM', 'selfHWHM', 'LowerEnergy',
                                        'airHWHMtempDependence', 'airPressureShift'],
                                 converters={'MoleculeNum':_int_converter, 'IsotopeNum':_int_converter,
                                             'wavenumber':_float_converter,
                                             'intensity':_float_converter, 'WeightedTransition':_float_converter,
                                             'airHWHM':_float_converter,
                                             'selfHWHM':_float_converter, 'LowerEnergy':_float_converter,
                                             'airHWHMtempDependence':_float_converter,
                                             'airPressureShift':_float_converter} )
    except:
        hitran = None  # in case the file is missing
    return hitran


txt = """
H2O  161,181,171,162,
CO2  626,636,628,627,638,637,828,728,
O3   666,668,686,667,676,
N2O  446,456,546,448,447,
CO   26,36,28,27,38,37,
CH4  211,311,212,
O2   66,68,67,
NO   46,56,48,
SO2  626,646,
NO2  646
NH3  4111,5111
HNO3 146
OH   61,81,62
HF   19
HCl  15,17
HBr  19,11
HI   17
ClO  56,76
OCS  622,624,632,623,822
H2CO 126,136,128
HOCl 165,167
N2   44
HCN  124,134,125
CH3Cl 215,217
H2O2  1661
C2H2  1221,1231
C2H6  1221
PH3   1111
COF2  269
SF6   29
H2S   121,141,131
HCOOH 126
HO2   166
O     6
ClONO2 5646,7646
NO+    46
HOBr 169,161
C2H4 221,231
CH3OH 216"""


molecules_to_process = ['H2O', 'CO2', 'O3', 'N2O', 'CH4', 'NO2']

hitran_molecules = {}
for i,curline in enumerate(txt.splitlines()):
    if i>0:
        isotopes = curline.split()[1]
        if isotopes.endswith(','):
            isotopes = isotopes[:-1]
        isotopes = isotopes.split(',')
        isotopes = dict(zip(range(1, len(isotopes) + 1, 1), isotopes))
        molecule_name = curline.split()[0]
        if molecule_name in molecules_to_process:
            hitran_molecules[i] = {'name':molecule_name, 'isotopes':isotopes,
                                   'hitran':get_hitran_molecule_number(i)}
                                   
# pandas rolling_max doesn't seem to work the way I want it to, so come up with some other scheme

atmos = pandas.io.parsers.read_csv(gzip.open('atmos.txt.gz', 'r'), sep='\t', skiprows=7, index_col='# wn')
wn_min = atmos.index.values.min()
wn_max = atmos.index.values.max()
w_breaks = np.where((atmos.index[1:].values - atmos.index[0:-1].values) > 1.0)
wn_starts = np.append(wn_min, atmos.index[(w_breaks[0] + 1,)])
wn_ends = np.append(atmos.index[(w_breaks[0],)].values, wn_max)
wn_ranges = zip(wn_starts, wn_ends)

comparison_range_halfwidth = 3.
comparison_max_ratio = 0.01
# lines that are not within comparison_max_ratio of the maximum line strength 
#     within approximately +- comparison_range_halfwidth will be deleted
#  ("approximately" because of how we bin to find the maximum)

for a in hitran_molecules:
    hitran = hitran_molecules[a]['hitran']
    mask = hitran['wavenumber'] < 0
    for cur_range in wn_ranges:
        mask = mask | ((hitran['wavenumber'] >= cur_range[0]) & (hitran['wavenumber'] <= cur_range[1]))
    hitran = hitran[mask]
    wn = np.arange(np.int(wn_min), np.ceil(wn_max), 1)
    local_max = pandas.Series(index=wn)
    for cur_wn in wn:
        local_max.ix[cur_wn] = hitran['intensity'][((hitran['wavenumber'] >= 
                                                     (cur_wn + 0.5 - comparison_range_halfwidth)) &
                                                    (hitran['wavenumber'] <= 
                                                     (cur_wn + 0.5 + comparison_range_halfwidth)))].max()
    hitran = hitran.ix[hitran['intensity'] >= 
                       comparison_max_ratio*local_max.ix[hitran['wavenumber'].map(np.int)]]         
    print hitran_molecules[a]['name'], len(hitran_molecules[a]['hitran']), len(hitran)
    f = gzip.open('hitran_abridged_' + hitran_molecules[a]['name'] + '.txt.gz', 'w')
    f.write('# comparison_range_halfwidth = ' + str(comparison_range_halfwidth) + '\n')
    f.write('# comparison_max_ratio = ' + str(comparison_max_ratio) + '\n')
    hitran.to_csv(f, cols=['wavenumber', 'intensity'], index=False)
    f.close()
    