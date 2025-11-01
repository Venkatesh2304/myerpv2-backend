//$(document).keydown(function (event) {
//    if (event.keyCode == 123) { // Prevent F12
//        return false;
//    } else if (event.ctrlKey && event.shiftKey && event.keyCode == 73) { // Prevent Ctrl+Shift+I        
//        return false;
//    }
//});
//$(document).keypress(
//    function (event) {
//        if (event.which == '13') {
//            event.preventDefault();
//        }
//    });

//$(document).on("contextmenu", function (e) {
//    e.preventDefault();
//});
$('.input_capital').on('input', function (evt) {
    $(this).val(function (_, val) {
        return val.toUpperCase();
    });
});
function blockSpecialChar(a) {
    var b;
    return b = document.all ? a.keyCode : a.which, b > 64 && b < 91 || b > 96 && b < 123 || 8 == b || 32 == b || b >= 48 && b <= 57
}

function isNumberKey(evt) {

    var charCode = (evt.which) ? evt.which : event.keyCode

    if (charCode > 31 && (charCode < 48 || charCode > 57) || charCode == 32) //charCode == 8 || - back space
        return false;

    return true;
}
function isDecimalNo(evt) {

    var charCode = (evt.which) ? evt.which : event.keyCode

    if (charCode > 31 && ((charCode < 48 && charCode != 46) || charCode > 57) || charCode == 32)
        return false;

    return true;
}
function isDecimalNoHsn(evt) {

    var charCode = (evt.which) ? evt.which : event.keyCode

    if (charCode > 30 && ((charCode < 48 && charCode != 46) || charCode > 57) || charCode == 32)
        return false;

    return true;
}
function isDecimalNoWithNeg(evt) {

    var charCode = (evt.which) ? evt.which : event.keyCode

    if (charCode > 31 && charCode != 45 && ((charCode < 48 && charCode != 46) || charCode > 57) || charCode == 32)
        return false;

    return true;
}
function blockalphabetsandnumbers(evt) {
    var charCode = (evt.which) ? evt.which : event.keyCode

    if (((keyCode >= 48 && keyCode <= 57) && isShift == false) ||
        (keyCode >= 65 && keyCode <= 90) || keyCode == 8 ||
        (keyCode >= 96 && keyCode <= 122))
        return false;

    return true;
}
function blockSpecialCharWithoutDashandBackSlash(evt) {

    var k = (evt.which) ? evt.which : event.keyCode;
    return ((k > 64 && k < 91) || (k > 96 && k < 123) || k == 8 || k == 46 || (k >= 48 && k <= 57) || k == 45 || k == 47);
}
function allowonlyAlphabet(evt) {
    var k = (evt.which) ? evt.which : event.keyCode;
    return (k > 64 &&  k < 91) || (k > 96 && k < 123)
}



