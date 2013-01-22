// Copyright (c) 2010, Amar Takhar <verm@aegisub.org>
//
// Permission to use, copy, modify, and distribute this software for any
// purpose with or without fee is hereby granted, provided that the above
// copyright notice and this permission notice appear in all copies.
//
// THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
// WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
// MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
// ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
// WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
// ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
// OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

/// @file util.cpp
/// @brief Windows utility methods.
/// @ingroup libaegisub windows

#include "../config.h"

#include "libaegisub/util.h"
#include "libaegisub/util_win.h"

#include "libaegisub/charset_conv_win.h"

namespace agi {
	namespace util {

using agi::charset::ConvertW;

std::string ErrorString(DWORD error) {
	LPWSTR lpstr = nullptr;

	if(FormatMessage(FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_FROM_SYSTEM, nullptr, error, 0, reinterpret_cast<LPWSTR>(&lpstr), 0, nullptr) == 0) {
		/// @todo Return the actual 'unknown error' string from windows.
		return "Unknown Error";
	}

	std::string str = ConvertW(lpstr);
	LocalFree(lpstr);
	return str;
}

/// @brief Get seconds and microseconds.
/// @param tv[out] agi_timeval struct
/// This code is from http://www.suacommunity.com/dictionary/gettimeofday-entry.php
agi_timeval time_log() {
#define DELTA_EPOCH_IN_MICROSECS  11644473600000000Ui64
	// Define a structure to receive the current Windows filetime
	FILETIME ft;

	// Initialize the present time to 0 and the timezone to UTC
	unsigned __int64 tmpres = 0;

	GetSystemTimeAsFileTime(&ft);

	// The GetSystemTimeAsFileTime returns the number of 100 nanosecond
	// intervals since Jan 1, 1601 in a structure. Copy the high bits to
	// the 64 bit tmpres, shift it left by 32 then or in the low 32 bits.
	tmpres |= ft.dwHighDateTime;
	tmpres <<= 32;
	tmpres |= ft.dwLowDateTime;

	// Convert to microseconds by dividing by 10
	tmpres /= 10;

	// The Unix epoch starts on Jan 1 1970.  Need to subtract the difference
	// in seconds from Jan 1 1601.
	tmpres -= DELTA_EPOCH_IN_MICROSECS;

	// Finally change microseconds to seconds and place in the seconds value.
	// The modulus picks up the microseconds.
	agi_timeval tv = { (long)(tmpres / 1000000UL), (long)(tmpres % 1000000UL) };
	return tv;
}

	} // namespace io
} // namespace agi
