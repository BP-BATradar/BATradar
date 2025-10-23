from core.microphone import Microphone


class Doa4:
    def __init__(self, mic1: Microphone, mic2: Microphone, mic3: Microphone, mic4: Microphone, doa: float) -> None:
        """
        Doa4 class represents a set of four microphones and the direction of arrival (DOA) of the sound source.

        Args:
            mic1 (Microphone): The first microphone.
            mic2 (Microphone): The second microphone.
            mic3 (Microphone): The third microphone.
            mic4 (Microphone): The fourth microphone.
            doa (float): The direction of arrival (DOA) of the sound source.
        """
        self.__mic1 = mic1
        self.__mic2 = mic2
        self.__mic3 = mic3
        self.__mic4 = mic4
        self.__doa = doa

    def __str__(self):
        """
        Returns:
            str: A string representation of the Doa4 object.
        """
        return f"(Doa4: mic1={self.__mic1.get_name()}, mic2={self.__mic2.get_name()}, mic3={self.__mic3.get_name()}, mic4={self.__mic4.get_name()}, doa={self.__doa:.2f})"

    def __repr__(self):
        """
        Returns:
            str: A string representation of the Doa4 object.
        """
        return str(self)

    def get_mic1(self) -> Microphone:
        """
        Returns:
            Microphone: The first microphone.
        """
        return self.__mic1

    def set_mic1(self, mic1: Microphone) -> None:
        """
        Args:
            mic1 (Microphone): The first microphone.
        """
        self.__mic1 = mic1

    def get_mic2(self) -> Microphone:
        """
        Returns:
            Microphone: The second microphone.
        """
        return self.__mic2

    def set_mic2(self, mic2: Microphone) -> None:
        """
        Args:
            mic2 (Microphone): The second microphone.
        """
        self.__mic2 = mic2

    def get_mic3(self) -> Microphone:
        """
        Returns:
            Microphone: The third microphone.
        """
        return self.__mic3

    def set_mic3(self, mic3: Microphone) -> None:
        """
        Args:
            mic3 (Microphone): The third microphone.
        """
        self.__mic3 = mic3  
    
    def get_mic4(self) -> Microphone:
        """
        Returns:
            Microphone: The fourth microphone.
        """
        return self.__mic4
    
    def set_mic4(self, mic4: Microphone) -> None:
        """
        Args:
            mic4 (Microphone): The fourth microphone.
        """
        self.__mic4 = mic4

    def get_doa(self) -> float:
        """
        Returns:
            float: The direction of arrival (DOA) of the sound source.
        """
        return self.__doa

    def set_doa(self, doa: float) -> None:
        """
        Args:
            doa (float): The direction of arrival (DOA) of the sound source.
        """
        self.__doa = doa
