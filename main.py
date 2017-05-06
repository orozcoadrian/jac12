import sys

from app import Jac
from infra import BclerkEfactsInfrastructure, ForeclosuresInfrastructure, EmailInfrastructure
from infra import FileSystemInfrastructure, BclerkPublicRecordsInfrastructure, BcpaoInfrastructure, TaxesInfrastructure


def main():
    jac = Jac(EmailInfrastructure(), ForeclosuresInfrastructure(), FileSystemInfrastructure(),
              BclerkEfactsInfrastructure(), BclerkPublicRecordsInfrastructure(), TaxesInfrastructure(),
              BcpaoInfrastructure())
    return jac.go()

    # legal = BclerkPublicRecords().get_legal_from_str('LT 11 BLK 3 PB 11 PG 39 WESTFIELD ESTATES SUB S 67 FT S 05 T 22 R 35 SUBID 04')
    # print(legal)

    # for c in ['05-2015-CA-022548-XXXX-XX']:
    #     jac.get_by_case_number(c)
    # return 0


if __name__ == '__main__':
    sys.exit(main())
