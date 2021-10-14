from loguru import logger


class Country2Flag:
    # This list of countries taken from OnlineSim's API page documentation: https://onlinesim.ru/docs/api/ru/sms/getNumbersStats#Result
    countries_flags_dict = {'7': '🇷🇺', '380': '🇺🇦', '49': '🇩🇪', '44': '🇬🇧', '33': '🇫🇷', '34': '🇪🇸', '46': '🇸🇪', '31': '🇳🇱', '45': '🇩🇰', '357': '🇨🇾', '1000': '🇨🇦', '1': '🇺🇸', '43': '🇦🇹', '420': '🇨🇿', '48': '🇵🇱', '40': '🇷🇴', '509': '🇭🇹', '212': '🇲🇦', '62': '🇮🇩', '63': '🇵🇭', '84': '🇻🇳', '371': '🇱🇻', '370': '🇱🇹', '372': '🇪🇪', '381': '🇷🇸', '373': '🇲🇩', '995': '🇬🇪', '996': '🇰🇬', '77': '🇰🇿', '52': '🇲🇽', '54': '🇦🇷', '90': '🇹🇷', '20': '🇪🇬', '972': '🇮🇱', '91': '🇮🇳', '967': '🇾🇪', '852': '🇭🇰', '234': '🇳🇬', '225': '🇨🇮', '998': '🇺🇿', '233': '🇬🇭', '359': '🇧🇬', '254': '🇰🇪', '57': '🇨🇴', '504': '🇭🇳', '92': '🇵🇰', '226': '🇧🇫', '992': '🇹🇯', '964': '🇮🇶', '353': '🇮🇪', '98': '🇮🇷', '994': '🇦🇿', '591': '🇧🇴', '94': '🇱🇰', '976': '🇲🇳', '977': '🇳🇵', '223': '🇲🇱', '235': '🇹🇩', '224': '🇬🇳', '30': '🇬🇷', '65': '🇸🇬', '375': '🇧🇾', '32': '🇧🇪', '237': '🇨🇲', '39': '🇮🇹', '86': '🇨🇳', '351': '🇵🇹', '593': '🇪🇨', '352': '🇱🇺', '377': '🇲🇨', '966': '🇸🇦', '41': '🇨🇭', '66': '🇹🇭', '421': '🇸🇰', '36': '🇭🇺'}

    def get(self, country_code):
        country_flag =  self.countries_flags_dict.get(country_code, "")

        if not country_flag:
            logger.error(f"Unknown country id: {country_code}")

        return country_flag
